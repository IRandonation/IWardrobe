import { useState, type FormEvent } from "react";
import { CloudUpload, Images, LoaderCircle, Plus } from "lucide-react";
import { api, categories, cutoutModel } from "../../lib/api";
import { ErrorBox } from "../../components/ui";

export function AddGarment({ onDone }: { onDone: (message: string) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [manual, setManual] = useState(false);
  const [autoCutout, setAutoCutout] = useState(true);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [pending, setPending] = useState(false);
  function choose(chosen: File[]) {
    setError("");
    if (chosen.some((f) => f.size > 20 * 1024 * 1024)) {
      setError("每张图片需小于 20 MB");
      return;
    }
    if (chosen.length > 20) {
      setError("每次最多添加 20 张图片");
      return;
    }
    setFiles(chosen);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.currentTarget);
    let completed = 0;
    try {
      if (manual) {
        await api("/garments", {
          method: "POST",
          body: JSON.stringify({
            name: form.get("name"),
            category: form.get("category"),
          }),
        });
        onDone("衣物已添加，随时可以补充详细信息");
      } else {
        if (!files.length) {
          setError("请先选择图片");
          return;
        }
        for (const [index, file] of files.entries()) {
          setProgress(`正在添加 ${index + 1} / ${files.length}`);
          const data = new FormData();
          data.set("file", file);
          if (autoCutout) data.set("cutout_model", cutoutModel);
          data.set(
            "name",
            file.name.replace(/\.[^.]+$/, "").slice(0, 100) || "新衣物",
          );
          await api("/garments/upload", { method: "POST", body: data });
          completed++;
        }
        onDone(
          `已添加 ${files.length} 件衣物，${autoCutout ? "抠图任务已排队，可在详情中对照并选用结果" : "缩略图将在后台处理"}`,
        );
      }
    } catch (e) {
      setFiles(files.slice(completed));
      setError(
        `${completed ? `已成功添加 ${completed} 件；剩余文件：` : ""}${(e as Error).message}`,
      );
    } finally {
      setPending(false);
      setProgress("");
    }
  }
  return (
    <form className="add-form" onSubmit={submit}>
      <p className="muted">一件衣物一张照片，细节可以之后慢慢补充。</p>
      <div className="segmented">
        <button
          type="button"
          className={!manual ? "selected" : ""}
          onClick={() => setManual(false)}
          disabled={pending}
        >
          上传照片
        </button>
        <button
          type="button"
          className={manual ? "selected" : ""}
          onClick={() => setManual(true)}
          disabled={pending}
        >
          手动建档
        </button>
      </div>
      {manual ? (
        <div className="form-grid">
          <label className="span-2">
            衣物名称
            <input
              name="name"
              required
              maxLength={100}
              placeholder="例如：奶白色圆领 T 恤"
            />
          </label>
          <label className="span-2">
            分类
            <select name="category">
              {Object.entries(categories).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <>
          <label
            className={`dropzone ${pending ? "disabled" : ""}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!pending) choose(Array.from(e.dataTransfer.files));
            }}
          >
            <CloudUpload size={38} strokeWidth={1.3} />
            <b>点击选择，或把照片拖到这里</b>
            <span>支持 JPEG、PNG、WebP · 每张不超过 20 MB</span>
            <input
              aria-label="选择衣物照片"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              disabled={pending}
              onChange={(e) => choose(Array.from(e.target.files ?? []))}
            />
          </label>
          {files.length > 0 && (
            <div className="file-list">
              {files.map((file, index) => (
                <div key={`${file.name}:${index}`}>
                  <Images size={16} />
                  <span>{file.name}</span>
                  <small>{(file.size / 1024 / 1024).toFixed(1)} MB</small>
                </div>
              ))}
            </div>
          )}
          <label className="upload-options">
            <input
              type="checkbox"
              checked={autoCutout}
              disabled={pending}
              onChange={(e) => setAutoCutout(e.target.checked)}
            />
            自动抠图
          </label>
          <p className="form-note">
            原图会保留。适合单件平铺或悬挂照片，穿着照可能保留人体。
            抠图在后台运行，完成后可在详情中对照、选用。取消勾选可暂不抠图。
          </p>
        </>
      )}
      {error && <ErrorBox text={error} />}
      <button
        className="button primary full"
        disabled={pending || (!manual && !files.length)}
      >
        {pending ? (
          <LoaderCircle className="spin" size={17} />
        ) : (
          <Plus size={17} />
        )}{" "}
        {progress ||
          (manual
            ? "创建衣物档案"
            : `添加${files.length ? ` ${files.length} 件` : ""}衣物`)}
      </button>
    </form>
  );
}
