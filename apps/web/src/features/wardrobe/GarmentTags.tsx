import type { Garment, Category } from "../../lib/api";

const tags = {
  warmth: {
    label: "厚薄",
    values: {
      unknown: "未确认",
      light: "薄",
      medium: "中等",
      warm: "厚 / 保暖",
    },
  },
  layer: {
    label: "穿着层次",
    values: { unknown: "未确认", base: "内搭", mid: "中层", outer: "外层" },
  },
  sleeve_length: {
    label: "袖长",
    values: {
      unknown: "未确认",
      sleeveless: "无袖",
      short: "短袖",
      long: "长袖",
    },
  },
  bottom_length: {
    label: "裤长 / 裙长",
    values: { unknown: "未确认", short: "短", long: "长" },
  },
  style: {
    label: "风格",
    values: {
      unknown: "未确认",
      casual: "休闲",
      smart: "通勤 / 正式",
      sport: "运动",
    },
  },
  rain_protection: {
    label: "防雨",
    values: { unknown: "未确认", yes: "有防雨能力", no: "不防雨" },
  },
  wind_protection: {
    label: "防风",
    values: { unknown: "未确认", yes: "有防风能力", no: "不防风" },
  },
};

export function GarmentTags({
  item,
  category,
}: {
  item: Garment;
  category: Category;
}) {
  const fields: (keyof typeof tags)[] = ["style"];
  if (["top", "bottom", "dress", "outerwear"].includes(category))
    fields.unshift("warmth");
  if (["top", "dress", "outerwear"].includes(category))
    fields.push("layer", "sleeve_length");
  if (["bottom", "dress"].includes(category)) fields.push("bottom_length");
  if (["top", "outerwear", "shoes"].includes(category))
    fields.push("rain_protection", "wind_protection");
  return (
    <details className="garment-tags">
      <summary>
        穿搭属性 <span>帮助判断天气与场合</span>
      </summary>
      <p className="form-note">
        按实际穿着和标签确认。不确定的项目保留“未确认”。
      </p>
      <div className="form-grid">
        {fields.map((field) => (
          <label key={field}>
            {tags[field].label}
            <select name={field} defaultValue={item[field] ?? "unknown"}>
              {Object.entries(tags[field].values).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </details>
  );
}
