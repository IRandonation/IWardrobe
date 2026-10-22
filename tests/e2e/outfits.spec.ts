import { test, expect } from "@playwright/test";
import fs from "node:fs";

test.use({ actionTimeout: 15000 });

const accounts = JSON.parse(
  fs.readFileSync(".local/outfit-e2e-accounts.json", "utf-8"),
);

test("逐时天气搭配的生成、换衣、穿着和可编辑反馈", async ({
  page,
  context,
}, testInfo) => {
  const account = accounts[testInfo.project.name];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("账号", { exact: true }).fill(account.username);
  await page.getByLabel("密码", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "进入我的衣橱" }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱." })).toBeVisible();
  const session = await (await context.request.get("/api/auth/me")).json();
  const headers = {
    "X-CSRF-Token": session.csrf_token,
    Origin: "http://127.0.0.1:5173",
  };
  const imported = await context.request.post("/api/demo/import", { headers });
  expect(imported.ok()).toBeTruthy();
  let garments = await (await context.request.get("/api/garments")).json();
  for (const item of garments) {
    const changed = await context.request.patch(`/api/garments/${item.id}`, {
      headers,
      data: {
        name: item.name,
        category: item.category,
        color: item.color,
        season: item.season,
        material: item.material,
        care: item.care,
        notes: item.notes,
        status: item.status,
        favorite: item.favorite,
        expected_version: item.version,
        warmth: "light",
        layer: item.category === "outerwear" ? "outer" : "base",
        sleeve_length: "long",
        bottom_length: "long",
        style: "casual",
        rain_protection: "no",
        wind_protection: "yes",
      },
    });
    expect(changed.ok()).toBeTruthy();
  }
  for (const [name, category, color] of [
    ["测试白色长袖", "top", "白色"],
    ["测试深蓝长裤", "bottom", "深蓝色"],
    ["测试棕色鞋", "shoes", "棕色"],
    ["测试轻薄外套", "outerwear", "米色"],
  ]) {
    if (garments.some((item: { name: string }) => item.name === name)) continue;
    const created = await context.request.post("/api/garments", {
      headers,
      data: {
        name,
        category,
        color,
        warmth: "light",
        layer: category === "outerwear" ? "outer" : "base",
        sleeve_length: "long",
        bottom_length: "long",
        style: "casual",
        rain_protection: "no",
        wind_protection: "yes",
      },
    });
    expect(created.ok()).toBeTruthy();
  }
  await page.reload();
  await expect(page.locator(".garment-card")).toHaveCount(8);
  const tagged = garments.find(
    (item: { category: string }) => item.category === "top",
  );
  await page
    .getByRole("button", { name: `查看${tagged.name}`, exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "单品详情" });
  await dialog.locator("summary").filter({ hasText: "穿搭属性" }).click();
  await dialog
    .getByRole("combobox", { name: "厚薄", exact: true })
    .selectOption("medium");
  await dialog.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByRole("status")).toContainText("衣物信息已保存");
  await dialog.getByRole("button", { name: "放入洗衣篮" }).click();
  await expect(dialog.getByText("待洗涤", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "已经洗净" }).click();
  await expect(dialog.getByText("可穿着", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "关闭弹窗" }).click();
  garments = await (await context.request.get("/api/garments")).json();
  expect(
    garments.find((item: { id: string }) => item.id === tagged.id).warmth,
  ).toBe("medium");

  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "今日穿搭", exact: true }).click();
  await expect(page.getByRole("heading", { name: "今日穿搭." })).toBeVisible();
  await page.getByRole("button", { name: "手动天气", exact: true }).click();
  await page.getByLabel("最低体感温度（℃）").fill("18");
  await page.getByLabel("最高体感温度（℃）").fill("24");
  await page
    .getByRole("combobox", { name: "返回时间", exact: true })
    .selectOption("19");
  await page.getByRole("button", { name: "生成搭配", exact: true }).click();
  await expect(page.locator(".outfit-card")).toHaveCount(3);
  await expect(page.locator(".weather-source")).toHaveText("手动天气");
  await expect(page.locator(".weather-summary")).toContainText("18—24℃");
  await expect(page.locator(".outfit-card img").first()).toBeVisible();
  let latest = await (
    await context.request.get("/api/recommendations/latest")
  ).json();
  const runId = latest.id;
  const firstCard = page.getByRole("article", {
    name: "搭配方案 1",
    exact: true,
  });
  const firstItem = latest.outfits[0].items[0];
  await firstCard
    .getByRole("button", { name: `换掉${firstItem.name}`, exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("已更换单品");
  latest = await (
    await context.request.get("/api/recommendations/latest")
  ).json();
  expect(
    latest.outfits[0].items.map((item: { id: string }) => item.id),
  ).not.toContain(firstItem.id);
  const wearing = latest.outfits[0].items;
  await firstCard
    .getByRole("button", { name: "今天穿这套", exact: true })
    .click();
  await expect(
    firstCard.getByRole("button", { name: "这套已记录" }),
  ).toBeDisabled();
  await expect(
    firstCard.getByRole("button", { name: /^换掉/ }).first(),
  ).toBeDisabled();
  garments = await (await context.request.get("/api/garments")).json();
  for (const item of wearing) {
    expect(
      garments.find((candidate: { id: string }) => candidate.id === item.id)
        .wear_count,
    ).toBe(item.wear_count + 1);
  }
  await firstCard.getByRole("button", { name: "偏冷", exact: true }).click();
  await expect(
    firstCard.getByRole("button", { name: "偏冷", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await firstCard.getByRole("button", { name: "合适", exact: true }).click();
  await expect(
    firstCard.getByRole("button", { name: "合适", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    firstCard.getByRole("button", { name: "偏冷", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await firstCard.getByRole("button", { name: "喜欢", exact: true }).click();
  await expect(
    firstCard.getByRole("button", { name: "喜欢", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("combobox", { name: "场合", exact: true })
    .selectOption("work");
  await page.waitForTimeout(5500);
  await expect(
    page.getByRole("combobox", { name: "场合", exact: true }),
  ).toHaveValue("work");
  await page.reload();
  await expect(page.getByRole("heading", { name: "今日穿搭." })).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "返回时间", exact: true }),
  ).toHaveValue("19");
  await expect(
    firstCard.getByRole("button", { name: "合适", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    firstCard.getByRole("button", { name: "喜欢", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  latest = await (
    await context.request.get("/api/recommendations/latest")
  ).json();
  expect(latest.id).toBe(runId);
  expect(latest.outfits[0].feedback).toEqual({
    comfort: "comfortable",
    liked: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `.local/screenshots/${testInfo.project.name}-outfits.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
