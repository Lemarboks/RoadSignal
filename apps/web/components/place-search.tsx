"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  searchPlaceSuggestions,
  type ResolvedPlace,
} from "../lib/open-routing";

type Props = {
  value: string;
  placeholder: string;
  resolved: ResolvedPlace | null;
  onChange: (value: string) => void;
  onResolved: (place: ResolvedPlace | null) => void;
};

export function PlaceSearch({
  value,
  placeholder,
  resolved,
  onChange,
  onResolved,
}: Props) {
  const listId = useId();
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [suggestions, setSuggestions] = useState<ResolvedPlace[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  function choosePlace(place: ResolvedPlace) {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    onChange(place.displayName);
    onResolved(place);
    setOpen(false);
    setActiveIndex(-1);
  }

  useEffect(() => {
    if (resolved || value.trim().length < 3) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      void searchPlaceSuggestions(value, controller.signal)
        .then((matches) => {
          setSuggestions(matches);
          setOpen(matches.length > 0);
          setActiveIndex(-1);
        })
        .catch(() => undefined)
        .finally(() => setLoading(false));
    }, 500);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [resolved, value]);

  return (
    <div className="place-search">
      <input
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          onResolved(null);
        }}
        onFocus={() => setOpen(suggestions.length > 0)}
        onKeyDown={(event) => {
          if (!open || !suggestions.length) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActiveIndex((index) => (index + 1) % suggestions.length);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActiveIndex((index) =>
              index <= 0 ? suggestions.length - 1 : index - 1,
            );
          } else if (event.key === "Enter" && activeIndex >= 0) {
            event.preventDefault();
            choosePlace(suggestions[activeIndex]);
          } else if (event.key === "Escape") {
            setOpen(false);
            setActiveIndex(-1);
          }
        }}
        onBlur={() => {
          blurTimer.current = setTimeout(() => setOpen(false), 150);
        }}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={
          activeIndex >= 0 ? `${listId}-option-${activeIndex}` : undefined
        }
      />
      {loading && <span className="place-search-status">Searching...</span>}
      {open && (
        <div className="place-suggestions" id={listId} role="listbox">
          {suggestions.map((place, index) => (
            <button
              id={`${listId}-option-${index}`}
              type="button"
              role="option"
              aria-selected={activeIndex === index}
              key={`${place.latitude}:${place.longitude}`}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choosePlace(place)}
            >
              <strong>{place.displayName.split(",")[0]}</strong>
              <span>{place.displayName.split(",").slice(1).join(",")}</span>
            </button>
          ))}
        </div>
      )}
      {resolved && (
        <small className="resolved-place">
          Matched: {resolved.displayName}
        </small>
      )}
    </div>
  );
}
