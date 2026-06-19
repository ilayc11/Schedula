import PropTypes from "prop-types";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./Tooltip.css";

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

export default function Tooltip({ text, children, className = "" }) {
  const anchorRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, placement: "top" });

  const enabled = Boolean(text);

  const updatePosition = () => {
    const el = anchorRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();

    const padding = 10;
    const gap = 10;
    const maxWidth = 360;

    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;

    // Base left centered over the anchor
    let left = rect.left + rect.width / 2;
    left = clamp(left, padding + maxWidth / 2, viewportW - padding - maxWidth / 2);

    // Prefer top, flip to bottom if not enough space
    const preferTop = rect.top > 120;
    const placement = preferTop ? "top" : "bottom";

    const top =
      placement === "top"
        ? rect.top - gap
        : rect.bottom + gap;

    setPos({ top, left, placement });
  };

  useEffect(() => {
    if (!open) return;

    updatePosition();

    const onScroll = () => updatePosition();
    const onResize = () => updatePosition();

    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  const bubble = useMemo(() => {
    if (!open || !enabled) return null;

    return (
      <div className="tt-layer" aria-hidden="true">
        <div
          className={`tt-bubble tt-${pos.placement}`}
          style={{ top: pos.top, left: pos.left, maxWidth: 360 }}
        >
          <div className="tt-text">{text}</div>
          <div className="tt-arrow" />
        </div>
      </div>
    );
  }, [open, enabled, pos.top, pos.left, pos.placement, text]);

  if (!enabled) return children;

  return (
    <>
      <span
        ref={anchorRef}
        className={`tt-anchor ${className}`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        {children}
      </span>

      {createPortal(bubble, document.body)}
    </>
  );
}

Tooltip.propTypes = {
  text: PropTypes.string,
  children: PropTypes.node.isRequired,
  className: PropTypes.string,
};
