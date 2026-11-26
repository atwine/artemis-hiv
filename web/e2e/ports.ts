// Where the browser tests' own servers listen: away from the dev ones (web 3000, API 8000, DB 5434).
const webPort = 3100;
const apiPort = 8100;

export const E2E = {
  webPort,
  apiPort,
  dbPort: 5435,
  webOrigin: `http://127.0.0.1:${webPort}`,
  apiUrl: `http://127.0.0.1:${apiPort}`,
} as const;
