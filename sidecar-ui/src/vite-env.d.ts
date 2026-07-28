/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SOAR_URL?: string;
  readonly VITE_SOAR_HANDLER_BASE?: string;
  readonly VITE_SOAR_USER?: string;
  readonly VITE_SOAR_PASS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
