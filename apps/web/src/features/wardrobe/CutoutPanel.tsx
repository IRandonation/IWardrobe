import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, Scissors } from "lucide-react";
import {
  api,
  cutoutModel,
  cutoutModelName,
  formatDuration,
  type CutoutModel,
  type Garment,
  type Job,
} from "../../lib/api";
import { ErrorBox } from "../../components/ui";

const jobLabels: Record<string, string> = {
  queued: "已排队",
  running: "正在抠图",
  succeeded: "已完成",
  failed: "处理失败",
};

export function CutoutPanel({
  item,
  jobs,
  onChanged,
}: {
  item: Garment;
  jobs: Job[];
  onChanged: (message: string) => void;
}) {
  const client = useQueryClient();
  const [previewModel, setPreviewModel] = useState<CutoutModel | null>(
    item.display_model === cutoutModel ? cutoutModel : null,
  );
  const [pending, setPending] = useState<"run" | "display" | null>(null);
  const [error, setError] = useState("");
  const selectedJob = jobs
    .filter(
      (job) => job.asset_id === item.asset_id && job.model === cutoutModel,
    )
    .sort(
      (a, b) =>
        Number(["queued", "running"].includes(b.status)) -
          Number(["queued", "running"].includes(a.status)) ||
        b.created_at.localeCompare(a.created_at),
    )[0];
  const busy =
    selectedJob && ["queued", "running"].includes(selectedJob.status);
  const result = item.cutouts.find((cutout) => cutout.model === cutoutModel);
  const imageUrl = previewModel ? result?.image_url : item.original_image_url;
  const isDisplay = item.display_model === previewModel;

  async function run() {
    setPending("run");
    setError("");
    try {
      const job =
        selectedJob?.status === "failed"
          ? await api<Job>(`/jobs/${selectedJob.id}/retry`, { method: "POST" })
          : await api<Job>(`/assets/${item.asset_id}/cutouts`, {
              method: "POST",
              body: JSON.stringify({ model: cutoutModel }),
            });
      client.setQueryData<Job[]>(["jobs"], (previous = []) => [
        job,
        ...previous.filter((entry) => entry.id !== job.id),
      ]);
      onChanged("抠图任务已排队");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(null);
    }
  }

  async function selectDisplay() {
    setPending("display");
    setError("");
    try {
      const updated = await api<Garment>(`/assets/${item.asset_id}/display`, {
        method: "PUT",
        body: JSON.stringify({ model: previewModel }),
      });
      client.setQueryData<Garment[]>(["garments"], (previous) =>
        previous?.map((garment) =>
          garment.id === updated.id ? updated : garment,
        ),
      );
      onChanged(previewModel ? "已将抠图设为衣橱展示图" : "已恢复原图展示");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="cutout-panel" aria-label="衣物照片抠图">
      <div className="cutout-tabs" role="group" aria-label="对照原图与抠图">
        <button
          type="button"
          aria-pressed={previewModel === null}
          className={previewModel === null ? "selected" : ""}
          onClick={() => setPreviewModel(null)}
        >
          原图
        </button>
        <button
          type="button"
          aria-pressed={previewModel === cutoutModel}
          className={previewModel === cutoutModel ? "selected" : ""}
          disabled={!result}
          onClick={() => setPreviewModel(cutoutModel)}
        >
          抠图结果
        </button>
      </div>
      <div
        className={`detail-photo cutout-preview ${previewModel ? "transparent" : item.category}`}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={`${item.name} · ${previewModel ? "抠图结果" : "原图"}`}
          />
        ) : (
          <span>暂无图片</span>
        )}
      </div>
      <div className="cutout-result">
        <span>
          {previewModel ? "透明背景" : "原始照片"}
          {previewModel &&
            result?.duration_ms != null &&
            ` · 耗时 ${formatDuration(result.duration_ms)}`}
        </span>
        {isDisplay ? (
          <span className="cutout-current">
            <Check size={13} /> 当前展示图
          </span>
        ) : (
          <button
            type="button"
            className="button small-button"
            disabled={pending !== null || !imageUrl}
            onClick={selectDisplay}
          >
            {pending === "display" && (
              <LoaderCircle className="spin" size={13} />
            )}
            {previewModel ? "设为展示图" : "恢复原图"}
          </button>
        )}
      </div>
      <div className="cutout-controls">
        <span className="cutout-model-name">{cutoutModelName}</span>
        <button
          type="button"
          className="button"
          disabled={pending !== null || !!busy}
          onClick={run}
        >
          {pending === "run" || busy ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Scissors size={15} />
          )}
          {busy
            ? jobLabels[selectedJob!.status]
            : selectedJob?.status === "failed"
              ? "重试抠图"
              : result
                ? "重新抠图"
                : "后台抠图"}
        </button>
      </div>
      <div className="cutout-status" aria-live="polite">
        {selectedJob && (
          <div className={selectedJob.status === "failed" ? "failed" : ""}>
            <span>{jobLabels[selectedJob.status] ?? selectedJob.status}</span>
            {selectedJob.status === "failed" && (
              <small>{selectedJob.error || "请重试抠图"}</small>
            )}
          </div>
        )}
      </div>
      {error && <ErrorBox text={error} />}
      <p className="form-note">
        适合单件平铺或悬挂照片，穿着照可能保留人体。抠图不展开褶皱，原图始终保留。
        处理完成后，切换上方图片对照并选用。
      </p>
    </section>
  );
}
