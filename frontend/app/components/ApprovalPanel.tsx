"use client";

import { useState } from "react";

type ApprovalPanelProps = {
  taskDescription: string;
  threadId: string;
  onSubmit: (decision: "approve" | "reject" | "edit", editedPlan?: string) => Promise<void>;
};

export function ApprovalPanel({
  taskDescription,
  threadId,
  onSubmit,
}: ApprovalPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedPlan, setEditedPlan] = useState(taskDescription);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAction = async (
    decision: "approve" | "reject" | "edit"
  ) => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (decision === "edit") {
        await onSubmit("edit", editedPlan);
      } else {
        await onSubmit(decision);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 space-y-4">
      <h3 className="text-sm font-medium text-amber-400 uppercase tracking-wider">
        Approval Required
      </h3>
      <p className="text-sm text-zinc-300">
        Review the plan before the Coder executes. Approve, edit, or reject.
      </p>

      {!isEditing ? (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-3">
          <p className="whitespace-pre-wrap text-zinc-200 text-sm">
            {taskDescription || "(No task description)"}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <label className="block text-sm text-zinc-400">
            Edit the plan
          </label>
          <textarea
            value={editedPlan}
            onChange={(e) => setEditedPlan(e.target.value)}
            rows={8}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-zinc-100 font-mono text-sm placeholder-zinc-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 resize-y"
            placeholder="Modify the plan as needed..."
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleAction("edit")}
              disabled={isSubmitting || !editedPlan.trim()}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? "Submitting…" : "Submit edited plan"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setEditedPlan(taskDescription);
              }}
              disabled={isSubmitting}
              className="rounded-lg border border-zinc-600 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              Cancel edit
            </button>
          </div>
        </div>
      )}

      {!isEditing && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleAction("approve")}
            disabled={isSubmitting}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? "Submitting…" : "Approve"}
          </button>
          <button
            type="button"
            onClick={() => handleAction("reject")}
            disabled={isSubmitting}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? "Submitting…" : "Reject"}
          </button>
          <button
            type="button"
            onClick={() => {
              setIsEditing(true);
              setEditedPlan(taskDescription);
            }}
            disabled={isSubmitting}
            className="rounded-lg border border-zinc-600 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-50 transition-colors"
          >
            Edit
          </button>
        </div>
      )}

      <p className="text-xs text-zinc-500 font-mono">thread_id: {threadId}</p>
    </div>
  );
}
