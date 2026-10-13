import { Shirt, Heart } from "lucide-react";
import { categories, seasons, statuses, type Garment } from "../../lib/api";

export function GarmentCard({
  item,
  onOpen,
  onFavorite,
}: {
  item: Garment;
  onOpen: () => void;
  onFavorite: () => void;
}) {
  return (
    <article className="garment-card">
      <div className={`garment-photo ${item.category}`}>
        <button
          className="photo-open"
          onClick={onOpen}
          aria-label={`查看${item.name}`}
        >
          {item.image_url ? (
            <img
              src={`${item.image_url}?ready=${item.image_ready}`}
              alt={item.name}
              loading="lazy"
            />
          ) : (
            <Shirt size={68} strokeWidth={1} />
          )}
        </button>
        {item.is_demo && <span className="demo-badge">演示</span>}
        <button
          className={`favorite-button ${item.favorite ? "is-favorite" : ""}`}
          aria-label={`${item.favorite ? "取消收藏" : "收藏"}${item.name}`}
          onClick={onFavorite}
        >
          <Heart size={18} fill={item.favorite ? "currentColor" : "none"} />
        </button>
        {!item.image_ready && item.image_url && (
          <span className="processing-badge">原图 · 缩略图处理中</span>
        )}
      </div>
      <button className="card-info" onClick={onOpen}>
        <div className="card-category">
          {categories[item.category]}
          <span>·</span>
          {seasons[item.season]}
        </div>
        <h3>{item.name}</h3>
        <div className="card-bottom">
          <span className={`status status-${item.status}`}>
            <i />
            {statuses[item.status]}
          </span>
          <span>穿过 {item.wear_count} 次</span>
        </div>
      </button>
    </article>
  );
}
