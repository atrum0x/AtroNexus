import { defineConfig } from "orval";

// Regenerate with `npm run gen:api` after changing the backend's routes or schemas.
export default defineConfig({
  api: {
    input: "./openapi.json",
    output: {
      mode: "tags-split",
      target: "src/api/generated/endpoints",
      schemas: "src/api/generated/models",
      client: "fetch",
      baseUrl: "",
      clean: true,
      override: {
        // Return the response body itself. The mutator throws ApiError on
        // any non-2xx status, so callers only ever see the success type.
        fetch: { includeHttpResponseReturnType: false },
        mutator: {
          path: "src/api/fetcher.ts",
          name: "apiFetch",
        },
      },
    },
  },
});
