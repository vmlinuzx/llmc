import { expect, test } from '@playwright/test';

test('template builder landing page renders core controls', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Template Builder MVP' })
  ).toBeVisible();

  await expect(
    page.getByRole('button', { name: /Generate LLMC Bundle/i })
  ).toBeEnabled();

  await expect(
    page.getByLabel('Project name')
  ).toHaveValue('template-builder-mvp');
});
