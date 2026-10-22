import { Check, RefreshCw, Shirt, ThumbsDown, ThumbsUp } from "lucide-react";
import { categories } from "../../lib/api";
import type { Feedback, Outfit } from "./api";

export function OutfitCard({
  outfit,
  index,
  pending,
  isToday,
  onSwap,
  onWear,
  onFeedback,
  onOpen,
}: {
  outfit: Outfit;
  index: number;
  pending: boolean;
  isToday: boolean;
  onSwap: (garmentId: string) => void;
  onWear: () => void;
  onFeedback: (feedback: Feedback) => void;
  onOpen: (garmentId: string) => void;
}) {
  const feedback = outfit.feedback ?? { comfort: null, liked: null };
  return (
    <article
      className={`outfit-card ${outfit.worn_at ? "is-worn" : ""}`}
      aria-label={`搭配方案 ${index + 1}`}
    >
      <header>
        <h3>方案 {index + 1}</h3>
        <span
          className={`outfit-badge ${outfit.stale || !outfit.complete ? "warning" : ""}`}
        >
          {outfit.worn_at
            ? "已记录穿着"
            : outfit.stale
              ? "衣物信息已变化"
              : outfit.complete
                ? "完整搭配"
                : "待补齐"}
        </span>
      </header>
      <div className="outfit-items">
        {outfit.items.map((item) => (
          <div className="outfit-item" key={item.id}>
            <button
              className={`outfit-item-image ${item.category}`}
              onClick={() => onOpen(item.id)}
              aria-label={`查看${item.name}`}
            >
              {item.image_url ? (
                <img src={item.image_url} alt={item.name} />
              ) : (
                <Shirt size={40} strokeWidth={1} />
              )}
            </button>
            <span className="outfit-item-category">
              {categories[item.category]}
            </span>
            <b>{item.name}</b>
            {item.is_demo && <small className="muted">演示衣物</small>}
            <button
              className="button small-button"
              disabled={pending || !!outfit.worn_at || outfit.stale}
              onClick={() => onSwap(item.id)}
              aria-label={`换掉${item.name}`}
            >
              <RefreshCw size={13} />
              换一件
            </button>
          </div>
        ))}
      </div>
      {!!outfit.reasons.length && (
        <ul className="outfit-reasons">
          {outfit.reasons.map((reason, i) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
      )}
      {!!outfit.warnings.length && (
        <ul className="outfit-warnings">
          {outfit.warnings.map((warning, i) => (
            <li key={i}>{warning}</li>
          ))}
        </ul>
      )}
      {outfit.stale && !outfit.worn_at && (
        <p className="outfit-notice">
          衣物已被修改或不再可穿，请重新生成搭配。
        </p>
      )}
      <button
        className="button primary full"
        disabled={
          pending ||
          !!outfit.worn_at ||
          outfit.stale ||
          !outfit.complete ||
          !isToday
        }
        onClick={onWear}
      >
        <Check size={16} />
        {outfit.worn_at ? "这套已记录" : "今天穿这套"}
      </button>
      {!isToday && !outfit.worn_at && (
        <p className="form-note">仅能记录推荐日期当天的实际穿着。</p>
      )}
      {!outfit.complete && (
        <p className="form-note">补齐缺少的单品后，重新生成搭配再记录。</p>
      )}
      <section
        className="outfit-feedback"
        aria-label={`方案 ${index + 1} 的穿着反馈`}
      >
        <b>穿着感受</b>
        {!outfit.worn_at && (
          <p className="muted">记录穿着后再反馈，帮助下次推荐。</p>
        )}
        <div className="feedback-choices" role="group" aria-label="冷热感受">
          {(
            [
              ["cold", "偏冷"],
              ["comfortable", "合适"],
              ["hot", "偏热"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              className={feedback.comfort === value ? "selected" : ""}
              disabled={pending || !outfit.worn_at}
              aria-pressed={feedback.comfort === value}
              onClick={() =>
                onFeedback({
                  ...feedback,
                  comfort: feedback.comfort === value ? null : value,
                })
              }
            >
              {label}
            </button>
          ))}
        </div>
        <div className="feedback-choices" role="group" aria-label="搭配喜好">
          <button
            disabled={pending || !outfit.worn_at}
            aria-pressed={feedback.liked === true}
            className={feedback.liked === true ? "selected" : ""}
            onClick={() =>
              onFeedback({
                ...feedback,
                liked: feedback.liked === true ? null : true,
              })
            }
          >
            <ThumbsUp size={14} />
            喜欢
          </button>
          <button
            disabled={pending || !outfit.worn_at}
            aria-pressed={feedback.liked === false}
            className={feedback.liked === false ? "selected" : ""}
            onClick={() =>
              onFeedback({
                ...feedback,
                liked: feedback.liked === false ? null : false,
              })
            }
          >
            <ThumbsDown size={14} />
            不喜欢
          </button>
        </div>
      </section>
    </article>
  );
}
