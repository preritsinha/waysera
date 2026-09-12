// Waysera runtime configuration.
// Plain script so the app needs no build step.

const WAYSERA_CONFIG = {
    // Where the relay is reachable. Leave blank for local work; the app then
    // assumes port 8000 on the host that served the page. Set it to the full
    // origin once the relay is deployed, for example:
    //   RELAY_URL: 'https://waysera-relay.fly.dev'
    //
    // It must be https/wss in production: a page served over HTTPS cannot open
    // a plaintext WebSocket, and the browser blocks it outright.
    RELAY_URL: '',

    // Stadia Maps key. Free tier, request at https://stadiamaps.com.
    //
    // Stadia serves unauthenticated requests when the referer is localhost,
    // which covers local development. That allowance is for development only —
    // a deployed site must carry a real key or every tile returns 401 and the
    // map does not render at all.
    STADIA_KEY: ''
};

window.WAYSERA_CONFIG = WAYSERA_CONFIG;
