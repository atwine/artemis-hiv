import { createCn } from "cn/config";

/**
 * Join class names; a later Tailwind class wins over an earlier one for the same property.
 * It is told the design's own scales (globals.css): without them, `text-13` reads as a colour
 * and `cn("text-13", "text-white")` drops the size.
 */
export const cn = createCn({
  extend: {
    classGroups: {
      "font-size": [{ text: ["11", "12", "13", "14", "15", "16", "20"] }],
      rounded: [{ rounded: ["logo", "chip", "btn", "window"] }],
      shadow: [{ shadow: ["window", "tray"] }],
    },
  },
});
