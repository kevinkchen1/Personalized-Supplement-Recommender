import { useMemo, useRef, useState } from "react";

type MultiSelectProps = {
  label: string;
  placeholder?: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
};

function normalize(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

export function MultiSelect({
  label,
  placeholder = "Search or add…",
  options,
  selected,
  onChange,
}: MultiSelectProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const normalizedSelected = useMemo(
    () => new Set(selected.map((s) => s.toLowerCase())),
    [selected],
  );

  const filteredOptions = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q
      ? options.filter((o) => o.toLowerCase().includes(q))
      : options;
    return base.filter((o) => !normalizedSelected.has(o.toLowerCase()));
  }, [options, query, normalizedSelected]);

  const canCreate = useMemo(() => {
    const v = normalize(query);
    if (!v) return false;
    const lower = v.toLowerCase();
    const existsInOptions = options.some((o) => o.toLowerCase() === lower);
    const existsInSelected = normalizedSelected.has(lower);
    return !existsInOptions && !existsInSelected;
  }, [options, query, normalizedSelected]);

  const addValue = (value: string) => {
    const v = normalize(value);
    if (!v) return;
    if (normalizedSelected.has(v.toLowerCase())) return;
    onChange([...selected, v]);
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  };

  const removeValue = (value: string) => {
    onChange(selected.filter((s) => s !== value));
  };

  return (
    <div className="ms">
      <label className="ms-label">{label}</label>

      {selected.length > 0 && (
        <div className="ms-tags">
          {selected.map((s) => (
            <span key={s} className="ms-tag">
              <span className="ms-tag-text">{s}</span>
              <button
                type="button"
                className="ms-tag-remove"
                onClick={() => removeValue(s)}
                aria-label={`Remove ${s}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="ms-inputRow">
        <input
          ref={inputRef}
          className="ms-input"
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (canCreate) addValue(query);
              else if (filteredOptions[0]) addValue(filteredOptions[0]);
            }
            if (e.key === "Escape") {
              setOpen(false);
            }
          }}
        />
        <button
          type="button"
          className="ms-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle options"
        >
          ▾
        </button>
      </div>

      {open && (
        <div className="ms-menu" role="listbox">
          {canCreate && (
            <button
              type="button"
              className="ms-item ms-item--create"
              onClick={() => addValue(query)}
            >
              Add “{normalize(query)}”
            </button>
          )}

          {filteredOptions.slice(0, 25).map((o) => (
            <button
              key={o}
              type="button"
              className="ms-item"
              onClick={() => addValue(o)}
            >
              {o}
            </button>
          ))}

          {!canCreate && filteredOptions.length === 0 && (
            <div className="ms-empty">No matches</div>
          )}
        </div>
      )}
    </div>
  );
}

