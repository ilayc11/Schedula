import { useEffect, useState } from "react";
import "./IntroAnimation.css";
import fullLogo from "../assets/fulllogo.png";

function IntroAnimation({ onFinish }) {
  const [isFadingOut, setIsFadingOut] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsFadingOut(true);
      setTimeout(onFinish, 800); // Wait for fade out animation to complete
    }, 2500);

    return () => clearTimeout(timer);
  }, [onFinish]);

  return (
    <div className={`intro-wrapper ${isFadingOut ? "fade-out" : ""}`}>
      <img src={fullLogo} alt="Schedula Full Logo" className="intro-logo" />
    </div>
  );
}

export default IntroAnimation;
