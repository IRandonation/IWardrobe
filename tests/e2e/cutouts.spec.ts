import { test, expect } from "@playwright/test";
import fs from "node:fs";
import type { components } from "../../apps/web/src/lib/generated";

type Garment = components["schemas"]["GarmentOut"];
type Job = components["schemas"]["JobOut"];

// These dedicated accounts are separate from wardrobe.spec.ts's empty-account setup.
const accounts = JSON.parse(
  fs.readFileSync(".local/cutout-e2e-accounts.json", "utf-8"),
);

test("BiRefNet 后台抠图、结果采纳与原图恢复", async ({
  page,
  context,
}, testInfo) => {
  test.setTimeout(180000);
  const account = accounts[testInfo.project.name];
  expect(account.username).toMatch(/^e2e-cutout-/);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("账号", { exact: true }).fill(account.username);
  await page.getByLabel("密码", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "进入我的衣橱" }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱." })).toBeVisible();

  // This synthetic fixture checks the real queue/inference path, not real-photo quality.
  const name = `cutout-${testInfo.project.name}-${Date.now()}`;
  await page.getByRole("button", { name: "添加衣物", exact: true }).click();
  const autoCutout = page.getByRole("checkbox", {
    name: "自动抠图",
    exact: true,
  });
  await expect(autoCutout).toBeChecked();
  await autoCutout.uncheck();
  await expect(autoCutout).not.toBeChecked();
  await autoCutout.check();
  await expect(
    page.getByRole("combobox", { name: "照片抠图", exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("选择衣物照片").setInputFiles({
    name: `${name}.png`,
    mimeType: "image/png",
    buffer: fs.readFileSync(
      process.env.CUTOUT_E2E_IMAGE || "fixtures/demo/images/oat-knit.png",
    ),
  });
  const uploaded = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/garments/upload") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "添加 1 件衣物" }).click();
  const uploadResponse = await uploaded;
  expect(uploadResponse.status()).toBe(201);
  const garment: Garment = await uploadResponse.json();
  expect(garment.asset_id).toBeTruthy();

  await page.getByRole("button", { name: `查看${name}`, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "单品详情" });
  const panel = dialog.getByRole("region", { name: "衣物照片抠图" });
  const notes = dialog.getByRole("textbox", { name: "备注", exact: true });
  const draft = "尚未保存的备注：后台完成与展示图切换不应清空。";
  await notes.fill(draft);
  await expect(panel.getByRole("combobox")).toHaveCount(0);
  await expect(panel.getByRole("button", { name: /U²-Netp/ })).toHaveCount(0);

  await expect
    .poll(
      async () => {
        const response = await context.request.get("/api/jobs");
        expect(response.ok()).toBe(true);
        const jobs: Job[] = await response.json();
        const cutouts = jobs.filter(
          (job) => job.asset_id === garment.asset_id && job.kind === "cutout",
        );
        const failed = cutouts.find((job) => job.status === "failed");
        if (failed) throw new Error(`${failed.model}: ${failed.error}`);
        return cutouts
          .filter((job) => job.status === "succeeded")
          .map((job) => job.model)
          .sort();
      },
      { timeout: 145000, intervals: [1000, 2000, 3000] },
    )
    .toEqual(["birefnet-general-lite"]);

  const detailResponse = await context.request.get(
    `/api/garments/${garment.id}`,
  );
  expect(detailResponse.ok()).toBe(true);
  const processed: Garment = await detailResponse.json();
  expect(processed.cutouts).toHaveLength(1);
  expect(processed.display_model).toBeNull();
  expect(processed.notes).toBe("");
  await expect(notes).toHaveValue(draft);

  const result = processed.cutouts[0];
  expect(result.model).toBe("birefnet-general-lite");
  expect(result.duration_ms).toBeGreaterThan(0);
  expect(result.model_version).toBeTruthy();
  const previewTab = panel.getByRole("button", {
    name: "抠图结果",
    exact: true,
  });
  await expect(previewTab).toBeEnabled();
  await previewTab.click();
  const preview = panel.getByRole("img");
  await expect(preview).toHaveAttribute("src", result.image_url);
  await expect
    .poll(() =>
      preview.evaluate(
        (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
      ),
    )
    .toBe(true);
  await expect(panel.getByText(/透明背景 · 耗时/)).toBeVisible();

  const imageResponse = await context.request.get(result.image_url);
  expect(imageResponse.status()).toBe(200);
  expect(imageResponse.headers()["content-type"]).toContain("image/png");
  expect(
    (await imageResponse.body())
      .subarray(0, 8)
      .equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
  ).toBe(true);

  const adopted = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/assets/${garment.asset_id}/display`) &&
      response.request().method() === "PUT",
  );
  await panel.getByRole("button", { name: "设为展示图", exact: true }).click();
  const adoptResponse = await adopted;
  expect(adoptResponse.status()).toBe(200);
  expect((await adoptResponse.json()).display_model).toBe(
    "birefnet-general-lite",
  );
  await expect(panel.getByText("当前展示图", { exact: true })).toBeVisible();
  await expect(notes).toHaveValue(draft);

  await panel.scrollIntoViewIfNeeded();
  await dialog.evaluate((element) => (element.scrollTop = 0));
  await page.screenshot({
    path: `.local/screenshots/${testInfo.project.name}-cutout.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);

  await panel.getByRole("button", { name: "原图", exact: true }).click();
  await expect(panel.getByRole("img")).toHaveAttribute(
    "src",
    processed.original_image_url!,
  );
  const restored = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/assets/${garment.asset_id}/display`) &&
      response.request().method() === "PUT",
  );
  await panel.getByRole("button", { name: "恢复原图", exact: true }).click();
  const restoreResponse = await restored;
  expect(restoreResponse.status()).toBe(200);
  expect((await restoreResponse.json()).display_model).toBeNull();
  await expect(notes).toHaveValue(draft);
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/garments/${garment.id}`) &&
      response.request().method() === "PATCH",
  );
  await dialog.getByRole("button", { name: "保存修改", exact: true }).click();
  expect((await saved).status()).toBe(200);
  await page.reload();
  await page.getByRole("button", { name: `查看${name}`, exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "原图", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(notes).toHaveValue(draft);
  expect(errors).toEqual([]);
});
