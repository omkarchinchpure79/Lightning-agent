"use client";

import { motion } from "framer-motion";

/**
 * Next.js App Router `template.tsx` — unlike layout, this re-mounts on every
 * navigation, so the content animates in each time the route changes.
 *
 * We animate entrance only (fade + slide-in from the right). True simultaneous
 * cross-fade of the outgoing page in the App Router requires freezing the router
 * during exit, which would block interaction — so we keep the entrance crisp and
 * let the old route unmount immediately. reducedMotion is honoured globally via
 * <MotionConfig reducedMotion="user"> in providers.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
