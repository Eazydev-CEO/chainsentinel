/**
 * SweetAlert2 dialogs themed for ChainSentinel — the only place native
 * confirm()/prompt() replacements live. Buttons reuse Bootstrap classes so
 * dialogs always match the app theme (styling in styles/globals.scss).
 */
import Swal from "sweetalert2";

function classes(danger: boolean, withInput = false) {
  return {
    popup: "cs-swal-popup",
    title: "cs-swal-title",
    htmlContainer: "cs-swal-text",
    actions: "cs-swal-actions",
    confirmButton: danger ? "btn btn-danger px-4" : "btn btn-primary px-4",
    cancelButton: "btn btn-outline-secondary",
    input: withInput ? "form-control cs-swal-input" : undefined,
    validationMessage: "cs-swal-validation",
  };
}

export interface ConfirmOptions {
  title: string;
  text?: string;
  confirmText?: string;
  cancelText?: string;
  /** Destructive action: red confirm button, warning icon, focus on Cancel. */
  danger?: boolean;
}

export async function confirmDialog({
  title,
  text,
  confirmText = "Confirm",
  cancelText = "Cancel",
  danger = false,
}: ConfirmOptions): Promise<boolean> {
  const result = await Swal.fire({
    title,
    text,
    icon: danger ? "warning" : "question",
    iconColor: danger ? "#ff5d5d" : "#4f8cff",
    showCancelButton: true,
    confirmButtonText: confirmText,
    cancelButtonText: cancelText,
    reverseButtons: true,
    focusCancel: danger,
    buttonsStyling: false,
    customClass: classes(danger),
  });
  return result.isConfirmed;
}

export interface PromptOptions {
  title: string;
  text?: string;
  placeholder?: string;
  confirmText?: string;
  cancelText?: string;
  initialValue?: string;
  danger?: boolean;
  /** Return an error message to block submission, or undefined to accept. */
  validate?: (value: string) => string | undefined;
}

export async function promptDialog({
  title,
  text,
  placeholder = "",
  confirmText = "Save",
  cancelText = "Cancel",
  initialValue = "",
  danger = false,
  validate,
}: PromptOptions): Promise<string | null> {
  const result = await Swal.fire({
    title,
    text,
    input: "text",
    inputPlaceholder: placeholder,
    inputValue: initialValue,
    showCancelButton: true,
    confirmButtonText: confirmText,
    cancelButtonText: cancelText,
    reverseButtons: true,
    buttonsStyling: false,
    customClass: classes(danger, true),
    inputValidator: validate
      ? (value) => validate(String(value ?? "")) ?? null
      : undefined,
  });
  return result.isConfirmed ? String(result.value ?? "") : null;
}

/** Small success toast for post-action feedback (top-right, auto-dismiss). */
export function toast(title: string, icon: "success" | "error" | "info" = "success"): void {
  void Swal.fire({
    title,
    icon,
    toast: true,
    position: "top-end",
    timer: 2400,
    timerProgressBar: true,
    showConfirmButton: false,
    customClass: { popup: "cs-swal-popup cs-swal-toast", title: "cs-swal-toast-title" },
  });
}
