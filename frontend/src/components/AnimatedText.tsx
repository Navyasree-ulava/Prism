import React, { useRef, useState } from "react";
import { motion } from "framer-motion";

interface AnimatedTextProps {
  text: string;
  down?: boolean;
  className?: string;
}

export const AnimatedText: React.FC<AnimatedTextProps> = ({
  text,
  down = false,
  className = "",
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLHeadingElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLHeadingElement>) => {
    const container = containerRef.current;
    if (!container) return;

    const letters = container.children;
    const containerRect = container.getBoundingClientRect();
    const mouseX = e.clientX - containerRect.left;

    Array.from(letters).forEach((letter, index) => {
      const letterRect = letter.getBoundingClientRect();
      const letterCenterX =
        letterRect.left + letterRect.width / 2 - containerRect.left;
      const distance = Math.abs(mouseX - letterCenterX);

      if (distance <= 18) {
        setHoveredIndex(index);
      }
    });
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
  };

  return (
    <motion.h1
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`font-bold flex items-center justify-center cursor-pointer text-[calc(1rem+14vw)] text-white uppercase leading-[calc(1rem+12.5vw)] select-none ${className}`}
      style={{
        fontFamily: "'Six Caps', sans-serif",
      }}
    >
      {text.split("").map((letter, index) => (
        <motion.span
          key={index}
          animate={{
            scaleY:
              hoveredIndex === null
                ? 1
                : Math.max(1, 1.3638 - Math.abs(index - hoveredIndex) * 0.08),
          }}
          transition={{
            type: "spring",
            stiffness: 140,
            damping: 22,
            mass: 0.8,
          }}
          style={{
            display: "inline-block",
            transformOrigin: down ? "top" : "bottom",
          }}
        >
          {letter}
        </motion.span>
      ))}
    </motion.h1>
  );
};

export default AnimatedText;
