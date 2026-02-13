"use client";

import { useEffect } from "react";

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error("Global error:", error);
    }, [error]);

    return (
        <html lang="en">
            <body>
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        minHeight: "100vh",
                        padding: "2rem",
                        fontFamily: "system-ui, sans-serif",
                    }}
                >
                    <h2 style={{ fontSize: "1.5rem", fontWeight: "bold", marginBottom: "0.5rem" }}>
                        Something went wrong
                    </h2>
                    <p style={{ color: "#666", marginBottom: "1.5rem" }}>
                        {error.message || "An unexpected error occurred."}
                    </p>
                    <div style={{ display: "flex", gap: "0.75rem" }}>
                        <button
                            onClick={() => reset()}
                            style={{
                                padding: "0.5rem 1rem",
                                border: "1px solid #ccc",
                                borderRadius: "0.375rem",
                                background: "white",
                                cursor: "pointer",
                            }}
                        >
                            Try Again
                        </button>
                        <a
                            href="/"
                            style={{
                                padding: "0.5rem 1rem",
                                border: "1px solid #333",
                                borderRadius: "0.375rem",
                                background: "#333",
                                color: "white",
                                textDecoration: "none",
                            }}
                        >
                            Back to Home
                        </a>
                    </div>
                </div>
            </body>
        </html>
    );
}
