import { useEffect, useRef, type ReactNode } from "react";
import { Shirt, LoaderCircle, X } from "lucide-react";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Shirt size={22} />
      </span>
      <span>
        IWardrobe<small>你的私人衣橱</small>
      </span>
    </div>
  );
}

export function Busy({ text = "正在整理衣橱…" }: { text?: string }) {
  return (
    <div className="busy">
      <LoaderCircle className="spin" size={22} />
      {text}
    </div>
  );
}

export function ErrorBox({ text }: { text: string }) {
  return (
    <div className="error" role="alert">
      {text}
    </div>
  );
}

export function Dialog({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = old;
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "wide" : ""}`}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog-inner">
        <header className="dialog-header">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="关闭弹窗"
            onClick={onClose}
          >
            <X size={21} />
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}
