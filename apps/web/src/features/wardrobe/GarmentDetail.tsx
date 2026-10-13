import { useState, type FormEvent } from "react";
import {
  Shirt,
  Sparkles,
  Check,
  WashingMachine,
  FolderArchive,
  LoaderCircle,
} from "lucide-react";
import {
  api,
  categories,
  seasons,
  statuses,
  updatePayload,
  type Garment,
} from "../../lib/api";
import { ErrorBox } from "../../components/ui";

export function GarmentDetail({
  item,
  onChanged,
  onClose,
}: {
  item: Garment;
  onChanged: (message: string) => void;
  onClose: () => void;
}) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function change(changes: Partial<Garment>, message: string) {
    setPending(true);
    setError("");
    try {
      await api(`/garments/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify(updatePayload(item, changes)),
      });
      onChanged(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    await change(data, "衣物信息已保存");
  }
  async function wear() {
    setPending(true);
    setError("");
    try {
      await api(`/garments/${item.id}/wear`, {
        method: "POST",
        body: JSON.stringify({ expected_version: item.version }),
      });
      onChanged("已记录一次穿着");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="detail-layout">
      <div className="detail-visual">
        <div className={`detail-photo ${item.category}`}>
          {item.image_url ? (
            <img src={item.image_url} alt={item.name} />
          ) : (
            <Shirt size={90} strokeWidth={1} />
          )}
        </div>
        <div className="detail-caption">
          <span className={`status status-${item.status}`}>
            <i />
            {statuses[item.status]}
          </span>
          <span>已穿 {item.wear_count} 次</span>
        </div>
        {item.is_demo && (
          <p className="demo-disclosure">
            <Sparkles size={16} />
            AI 生成演示图片。材质、护理为示例数据，未经识别验证。
          </p>
        )}
        <div className="detail-actions">
          <button
            className="button"
            disabled={pending || item.status !== "available"}
            onClick={wear}
          >
            <Check size={16} />
            今天穿过
          </button>
          <button
            className="button"
            disabled={pending}
            onClick={() =>
              change(
                { status: item.status === "laundry" ? "available" : "laundry" },
                item.status === "laundry"
                  ? "已洗净，重新回到可穿衣橱"
                  : "已放入洗衣篮",
              )
            }
          >
            <WashingMachine size={16} />
            {item.status === "laundry" ? "已经洗净" : "放入洗衣篮"}
          </button>
          <button
            className="button text-button"
            disabled={pending}
            onClick={() =>
              change(
                {
                  status: item.status === "archived" ? "available" : "archived",
                },
                item.status === "archived" ? "已恢复到衣橱" : "已放入收纳箱",
              )
            }
          >
            <FolderArchive size={16} />
            {item.status === "archived" ? "恢复到衣橱" : "暂时收纳"}
          </button>
        </div>
      </div>
      <form className="detail-form" onSubmit={save}>
        <div className="form-grid">
          <label className="span-2">
            衣物名称
            <input
              name="name"
              defaultValue={item.name}
              required
              maxLength={100}
            />
          </label>
          <label>
            分类
            <select name="category" defaultValue={item.category}>
              {Object.entries(categories).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            季节
            <select name="season" defaultValue={item.season}>
              {Object.entries(seasons).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            颜色
            <input name="color" defaultValue={item.color} maxLength={40} />
          </label>
          <label>
            材质
            <input
              name="material"
              defaultValue={item.material}
              maxLength={120}
              placeholder="按真实标签填写"
            />
          </label>
          <label className="span-2">
            洗涤与护理
            <textarea
              name="care"
              defaultValue={item.care}
              maxLength={500}
              rows={2}
              placeholder="记录洗标上的护理要求"
            />
          </label>
          <label className="span-2">
            备注
            <textarea
              name="notes"
              defaultValue={item.notes}
              maxLength={1000}
              rows={2}
              placeholder="购买记录、搭配想法…"
            />
          </label>
        </div>
        {error && <ErrorBox text={error} />}
        <div className="form-footer">
          <button type="button" className="button" onClick={onClose}>
            关闭
          </button>
          <button className="button primary" disabled={pending}>
            {pending ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Check size={16} />
            )}
            保存修改
          </button>
        </div>
      </form>
    </div>
  );
}
