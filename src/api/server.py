from typing import Any, Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.graph.connections import graph_interface, schema_provider  # noqa: F401
from src.workflow.graph_builder import build_workflow
from src.workflow.state import ConversationState, InputState, create_initial_state


load_dotenv()

# Build LangGraph workflow once at startup
workflow = build_workflow()


class PatientProfile(BaseModel):
    medications: str = ""
    supplements: str = ""
    conditions: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    user_question: str
    patient_profile: PatientProfile
    # Included for future session/memory support; not yet persisted
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    final_answer: Optional[str]
    safety_results: Optional[Dict[str, Any]] = None
    deficiency_results: Optional[Dict[str, Any]] = None
    recommendation_results: Optional[Dict[str, Any]] = None
    evidence_chain: List[str] = Field(default_factory=list)
    iterations: int = 0
    error_message: Optional[str] = None


app = FastAPI(title="Supplement Safety Advisor API")


# CORS – allow local dev frontends by default; configure for prod later
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",  # Create React App / Next dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """
    Run a full LangGraph workflow execution for a single question + profile.

    This is currently stateless per request; session_id is reserved for
    future persistent memory / multi-turn conversations.
    """
    try:
        input_state: InputState = {
            "user_question": payload.user_question,
            "patient_profile": payload.patient_profile.model_dump(),
        }

        initial_state: ConversationState = create_initial_state(
            user_question=input_state["user_question"],
            patient_profile=input_state["patient_profile"],
        )

        result: ConversationState = workflow.invoke(initial_state)  # type: ignore[arg-type]

        return ChatResponse(
            final_answer=result.get("final_answer"),
            safety_results=result.get("safety_results"),
            deficiency_results=result.get("deficiency_results"),
            recommendation_results=result.get("recommendation_results"),
            evidence_chain=result.get("evidence_chain", []),
            iterations=result.get("iterations", 0),
            error_message=result.get("error_message"),
        )
    except Exception as exc:  # noqa: BLE001
        # For now, surface a generic error to the client and log server-side
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def run():
    """Convenience entrypoint for `pdm run api`."""
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()

