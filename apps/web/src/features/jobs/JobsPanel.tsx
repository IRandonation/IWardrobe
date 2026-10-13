import { useState } from "react";
import { CheckCircle2, LoaderCircle, Images } from "lucide-react";
import { api, type Job } from "../../lib/api";
import { ErrorBox } from "../../components/ui";

export function JobsPanel({
  jobs,
  error,
  refresh,
  notify,
}: {
  jobs: Job[];
  error?: string;
  refresh: () => void;
  notify: (message: string) => void;
}) {
  const [retrying, setRetrying] = useState<string | null>(null);
  const [failure, setFailure] = useState("");
  async function retry(id: string) {
    setRetrying(id);
    setFailure("");
    try {
      await api(`/jobs/${id}/retry`, { method: "POST" });
      refresh();
      notify("任务已重新排队");
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setRetrying(null);
    }
  }
  const labels: Record<string, string> = {
    queued: "等待处理",
    running: "正在处理",
    succeeded: "已完成",
    failed: "处理失败",
  };
  return (
    <section className="jobs-panel">
      <div className="section-title">
        <h2>图片处理记录</h2>
        <span>最近 100 条 · 自动更新</span>
      </div>
      <p className="muted">
        缩略图由后台生成，等待期间仍可查看原图和编辑衣物。
      </p>
      {(error || failure) && <ErrorBox text={error || failure} />}{" "}
      {jobs.length ? (
        jobs.map((job) => (
          <div className="job-row" key={job.id}>
            <span className={`job-icon ${job.status}`}>
              {job.status === "succeeded" ? (
                <CheckCircle2 size={22} />
              ) : job.status === "running" ? (
                <LoaderCircle className="spin" size={22} />
              ) : (
                <Images size={22} />
              )}
            </span>
            <div>
              <b>衣物缩略图</b>
              <small>
                {new Date(job.created_at).toLocaleString("zh-CN")}
                {job.error ? ` · ${job.error}` : ""}
              </small>
            </div>
            <span>{labels[job.status] ?? job.status}</span>
            {job.status === "failed" && (
              <button
                className="button small-button"
                disabled={retrying === job.id}
                onClick={() => retry(job.id)}
              >
                重试
              </button>
            )}
          </div>
        ))
      ) : (
        <div className="empty">
          <Images size={32} />
          <h3>还没有图片任务</h3>
          <p>上传照片或导入演示衣物后，可在这里查看进度。</p>
        </div>
      )}
    </section>
  );
}
