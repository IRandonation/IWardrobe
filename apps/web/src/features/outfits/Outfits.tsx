import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CloudSun,
  Droplets,
  LoaderCircle,
  MapPin,
  Search,
  Thermometer,
  Wind,
} from "lucide-react";
import { api } from "../../lib/api";
import { Busy, ErrorBox } from "../../components/ui";
import {
  exposures,
  localDate,
  occasions,
  thermalPreferences,
  weatherSources,
  type Location,
  type Preferences,
  type Run,
} from "./api";
import { OutfitCard } from "./OutfitCard";

const latestKey = ["recommendations", "latest"];
const preferencesKey = ["recommendations", "preferences"];

export function Outfits({
  onOpen,
  notify,
}: {
  onOpen: (id: string) => void;
  notify: (message: string) => void;
}) {
  const preferences = useQuery({
    queryKey: preferencesKey,
    queryFn: () => api<Preferences>("/recommendations/preferences"),
    refetchOnWindowFocus: false,
  });
  if (preferences.isPending) return <Busy />;
  if (preferences.isError)
    return (
      <div className="outfit-settings">
        <ErrorBox text={preferences.error.message} />
        <button className="button" onClick={() => preferences.refetch()}>
          重新加载
        </button>
      </div>
    );
  return (
    <OutfitPlanner initial={preferences.data} onOpen={onOpen} notify={notify} />
  );
}

function OutfitPlanner({
  initial,
  onOpen,
  notify,
}: {
  initial: Preferences;
  onOpen: (id: string) => void;
  notify: (message: string) => void;
}) {
  const client = useQueryClient();
  const [settings, setSettings] = useState(initial);
  const [date, setDate] = useState(() => localDate(initial.location?.timezone));
  const [manual, setManual] = useState(false);
  const [weatherInput, setWeatherInput] = useState({
    feels_min: 16,
    feels_max: 24,
    rain_probability: 0,
    wind_kph: 0,
  });
  const [query, setQuery] = useState("");
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const latest = useQuery({
    queryKey: latestKey,
    queryFn: () => api<Run | null>("/recommendations/latest"),
    refetchOnWindowFocus: true,
  });
  const run = latest.data;

  async function searchLocations() {
    if (query.trim().length < 2) {
      setLocationError("请输入至少两个字符，例如北京或 Shanghai。");
      return;
    }
    setSearching(true);
    setLocationError("");
    setLocations(null);
    try {
      setLocations(
        await api<Location[]>(
          `/weather/locations?q=${encodeURIComponent(query.trim())}`,
        ),
      );
    } catch (e) {
      setLocationError(`${(e as Error).message}；可切换为手动天气。`);
    } finally {
      setSearching(false);
    }
  }

  async function savePreferences() {
    const saved = await api<Preferences>("/recommendations/preferences", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
    client.setQueryData(preferencesKey, saved);
  }

  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!manual && !settings.location) {
      setError("请先搜索并选择城市，或切换为手动天气。");
      return;
    }
    if (settings.start_hour === settings.end_hour) {
      setError("出门和返回时间不能相同。");
      return;
    }
    if (manual && weatherInput.feels_min > weatherInput.feels_max) {
      setError("最低体感温度不能高于最高体感温度。");
      return;
    }
    setPending(true);
    setError("");
    try {
      await savePreferences();
      const result = await api<Run>("/recommendations", {
        method: "POST",
        body: JSON.stringify({
          weather: {
            location: settings.location,
            date,
            start_hour: settings.start_hour,
            end_hour: settings.end_hour,
            manual: manual ? weatherInput : null,
          },
          occasion: settings.occasion,
          exposure: settings.exposure,
          thermal_preference: settings.thermal_preference,
        }),
      });
      client.setQueryData(latestKey, result);
      notify("搭配已生成，出行默认设置已保存");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }

  async function mutate(outfitId: string, action: string, body?: unknown) {
    if (!run) return;
    setPending(true);
    setError("");
    try {
      const updated = await api<Run>(
        `/recommendations/${run.id}/outfits/${outfitId}/${action}`,
        {
          method: action === "feedback" ? "PUT" : "POST",
          body: body === undefined ? undefined : JSON.stringify(body),
        },
      );
      client.setQueryData(latestKey, updated);
      if (action === "wear")
        void client.invalidateQueries({ queryKey: ["garments"] });
      notify(
        action === "swap"
          ? "已更换单品"
          : action === "wear"
            ? "已记录整套穿着，可以填写感受了"
            : "反馈已保存，再次点选可修改或清除",
      );
    } catch (e) {
      setError((e as Error).message);
      void latest.refetch();
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="outfits-page">
      <form className="outfit-settings" onSubmit={generate}>
        <div className="outfit-section-heading">
          <CloudSun size={22} />
          <div>
            <h2>安排今天的出行</h2>
            <p className="muted">
              根据时段内的体感温度、风雨和你的衣橱组合搭配。
            </p>
          </div>
        </div>
        <fieldset disabled={pending}>
          <div
            className="segmented weather-mode"
            role="group"
            aria-label="天气来源"
          >
            <button
              type="button"
              className={!manual ? "selected" : ""}
              aria-pressed={!manual}
              onClick={() => setManual(false)}
            >
              城市预报
            </button>
            <button
              type="button"
              className={manual ? "selected" : ""}
              aria-pressed={manual}
              onClick={() => setManual(true)}
            >
              手动天气
            </button>
          </div>
          {!manual ? (
            <div className="location-picker">
              <div className="form-grid location-search">
                <label>
                  搜索城市
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="例如：北京 / Shanghai"
                    maxLength={100}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void searchLocations();
                      }
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="button"
                  disabled={searching}
                  onClick={searchLocations}
                >
                  {searching ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <Search size={16} />
                  )}
                  搜索城市
                </button>
              </div>
              {locationError && <ErrorBox text={locationError} />}
              {locations && (
                <div className="location-results" aria-label="城市搜索结果">
                  {locations.length ? (
                    locations.map((location) => (
                      <button
                        type="button"
                        key={`${location.latitude}:${location.longitude}`}
                        onClick={() => {
                          setSettings({ ...settings, location });
                          setLocations(null);
                          setQuery("");
                        }}
                      >
                        <MapPin size={15} />
                        <span>
                          {location.label}
                          <small>{location.timezone}</small>
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="muted">没有匹配的城市，可尝试英文名称。</p>
                  )}
                </div>
              )}
              <p className="location-selected">
                <MapPin size={15} />
                {settings.location
                  ? `${settings.location.label} · ${settings.location.timezone}`
                  : "尚未选择城市"}
              </p>
              <p className="form-note">
                城市名称和坐标会发送至 Open-Meteo 获取预报，衣物和照片留在本机。
              </p>
            </div>
          ) : (
            <div className="manual-weather">
              <p className="form-note">
                手动天气用于试用或离线场景，不代表实时预报。填写预计出行时段的体感温度。
              </p>
              <div className="form-grid weather-input-grid">
                <label>
                  最低体感温度（℃）
                  <input
                    type="number"
                    required
                    min={-60}
                    max={60}
                    step="0.1"
                    value={weatherInput.feels_min}
                    onChange={(e) =>
                      setWeatherInput({
                        ...weatherInput,
                        feels_min: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  最高体感温度（℃）
                  <input
                    type="number"
                    required
                    min={-60}
                    max={60}
                    step="0.1"
                    value={weatherInput.feels_max}
                    onChange={(e) =>
                      setWeatherInput({
                        ...weatherInput,
                        feels_max: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  降雨概率（%）
                  <input
                    type="number"
                    required
                    min={0}
                    max={100}
                    value={weatherInput.rain_probability}
                    onChange={(e) =>
                      setWeatherInput({
                        ...weatherInput,
                        rain_probability: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  最大风速（km/h）
                  <input
                    type="number"
                    required
                    min={0}
                    max={300}
                    value={weatherInput.wind_kph}
                    onChange={(e) =>
                      setWeatherInput({
                        ...weatherInput,
                        wind_kph: Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
            </div>
          )}
          <div className="form-grid trip-settings">
            <label>
              出行日期
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label>
              出门时间
              <select
                value={settings.start_hour}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    start_hour: Number(e.target.value),
                  })
                }
              >
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {String(hour).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </label>
            <label>
              返回时间
              <select
                value={settings.end_hour}
                onChange={(e) =>
                  setSettings({ ...settings, end_hour: Number(e.target.value) })
                }
              >
                {Array.from({ length: 25 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {String(hour).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </label>
            <label>
              场合
              <select
                value={settings.occasion}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    occasion: e.target.value as Preferences["occasion"],
                  })
                }
              >
                {Object.entries(occasions).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              活动环境
              <select
                value={settings.exposure}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    exposure: e.target.value as Preferences["exposure"],
                  })
                }
              >
                {Object.entries(exposures).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              冷热倾向
              <select
                value={settings.thermal_preference}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    thermal_preference: e.target
                      .value as Preferences["thermal_preference"],
                  })
                }
              >
                {Object.entries(thermalPreferences).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {settings.end_hour < settings.start_hour && (
            <p className="form-note">
              返回时间为次日 {String(settings.end_hour).padStart(2, "0")}:00。
            </p>
          )}
          <p className="form-note">
            日期按 {settings.location?.timezone ?? "Asia/Shanghai"}{" "}
            计算。出行设置会在生成时保存。
          </p>
          <div className="outfit-generate">
            <button className="button primary" type="submit">
              {pending ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <CloudSun size={17} />
              )}
              {pending ? "正在处理…" : "生成搭配"}
            </button>
            <span className="muted">最多三套，仅使用当前账号可穿的衣物。</span>
          </div>
        </fieldset>
      </form>
      {error && <ErrorBox text={error} />}
      {latest.isError && (
        <ErrorBox text={`上次搭配加载失败：${latest.error.message}`} />
      )}
      {latest.isPending ? (
        <Busy />
      ) : run ? (
        <section className="outfit-results" aria-label="推荐结果">
          <div className="outfit-result-heading">
            <h2>你的搭配方案</h2>
            <span className={`weather-source ${run.weather.source}`}>
              {weatherSources[run.weather.source]}
            </span>
          </div>
          <div className="weather-summary">
            <div>
              <b>{run.weather.location_name}</b>
              <p>
                {run.weather.date} ·{" "}
                {String(run.weather.start_hour).padStart(2, "0")}:00—
                {run.weather.end_hour < run.weather.start_hour ? "次日 " : ""}
                {String(run.weather.end_hour).padStart(2, "0")}:00 ·{" "}
                {occasions[run.occasion]}
              </p>
            </div>
            <span>
              <Thermometer size={16} />
              体感 {run.weather.feels_min}—{run.weather.feels_max}℃
            </span>
            <span>
              <Droplets size={16} />
              降雨 {run.weather.rain_probability}%
            </span>
            <span>
              <Wind size={16} />
              风速 {run.weather.wind_kph} km/h
            </span>
          </div>
          {run.weather.fetched_at && (
            <p className="form-note">
              预报获取于{" "}
              {new Date(run.weather.fetched_at).toLocaleString("zh-CN", {
                timeZone: run.weather.timezone,
              })}
              （{run.weather.timezone}）
            </p>
          )}
          {run.weather.source !== "manual" && (
            <p className="form-note">
              天气数据：
              <a
                href="https://open-meteo.com/"
                target="_blank"
                rel="noreferrer"
              >
                Open-Meteo
              </a>{" "}
              ·{" "}
              <a
                href="https://creativecommons.org/licenses/by/4.0/"
                target="_blank"
                rel="noreferrer"
              >
                CC BY 4.0
              </a>
            </p>
          )}
          {[...new Set([...(run.weather.warnings ?? []), ...run.warnings])].map(
            (warning, i) => (
              <p className="outfit-notice" key={i}>
                {warning}
              </p>
            ),
          )}
          <p className="outfit-learning muted">{run.learning_note}</p>
          {run.outfits.length ? (
            <div className="outfit-grid">
              {run.outfits.map((outfit, index) => (
                <OutfitCard
                  key={outfit.id}
                  outfit={outfit}
                  index={index}
                  pending={pending}
                  isToday={run.weather.date === localDate(run.weather.timezone)}
                  onOpen={onOpen}
                  onSwap={(garmentId) =>
                    void mutate(outfit.id, "swap", { garment_id: garmentId })
                  }
                  onWear={() => void mutate(outfit.id, "wear")}
                  onFeedback={(feedback) =>
                    void mutate(outfit.id, "feedback", feedback)
                  }
                />
              ))}
            </div>
          ) : (
            <div className="empty">
              <CloudSun size={32} />
              <h3>暂时没有合适搭配</h3>
              <p>补充可穿衣物，并在单品详情里确认厚薄、层次和风格后再试。</p>
            </div>
          )}
          <p className="form-note">
            这是上次生成的结果。修改上方设置后，点击“生成搭配”更新。
          </p>
        </section>
      ) : (
        <div className="outfit-start">
          <CloudSun size={34} />
          <h3>从天气和衣橱开始</h3>
          <p>
            选择城市或手动填写天气，生成适合你的搭配。衣物属性可在单品详情的“穿搭属性”中补充。
          </p>
        </div>
      )}
    </div>
  );
}
