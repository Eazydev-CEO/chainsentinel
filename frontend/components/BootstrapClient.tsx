"use client";

import { useEffect } from "react";

/** Loads Bootstrap's JS (dropdowns, offcanvas, collapse) client-side only. */
export default function BootstrapClient() {
  useEffect(() => {
    // @ts-expect-error — no bundled types for the dist build
    void import("bootstrap/dist/js/bootstrap.bundle.min.js");
  }, []);
  return null;
}
