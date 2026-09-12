// Waysera runtime configuration — Android app.
//
// Both values below MUST be real public URLs. Inside the packaged app the page
// is served from https://localhost, so anything left blank would resolve to the
// phone itself, where nothing is listening.

const WAYSERA_CONFIG = {
    // WebSocket relay the app connects to.
    //   e.g. 'https://waysera-relay.onrender.com'
    //
    // Left empty the app falls back to ws://localhost:8000 — nothing listens
    // there on a phone, so it retries with backoff and the group stays empty.
    // Everything else still works: map, search, routing, your own position.
    //
    // Do not put a placeholder string here. Any non-empty value is used
    // verbatim, and one without a ws/wss scheme makes the WebSocket
    // constructor throw instead of failing quietly.
    RELAY_URL: 'http://10.0.2.2:8000',

    // Public web deployment used to mint invite links. Recipients open these
    // in a browser, so it must not be localhost.
    //   e.g. 'https://waysera.pages.dev'
    //
    // Optional. Left empty, invite links point at https://localhost and are
    // useless, but joining by six-character code still works normally.
    PUBLIC_ORIGIN: '',


    // Stadia Maps key. Free tier, request at https://stadiamaps.com.
    //
    // Stadia serves unauthenticated requests when the referer is localhost,
    // which covers local development and the Android app (a Capacitor WebView
    // reports http://localhost). That allowance is for development. A released
    // build must carry a real key, or tiles will 401 for every user.
    STADIA_KEY: ''
};

window.WAYSERA_CONFIG = WAYSERA_CONFIG;
