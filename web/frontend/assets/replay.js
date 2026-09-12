/**
 * Waysera journey replay.
 *
 * Plays a finished journey back from this device's own recording. Nothing is
 * fetched: every participant received everyone's positions while the journey
 * was running, so each device already holds a complete copy.
 *
 * Positions are recorded every few seconds, so playback interpolates between
 * them. Without that, markers would jump instead of moving.
 */

(() => {
    'use strict';

    const SPEEDS = [1, 2, 5, 10];

    let journey = null;
    let tracks = new Map();
    let events = [];
    let names = new Map();

    let startTs = 0;
    let endTs = 0;
    let currentTs = 0;

    let playing = false;
    let speed = 1;
    let lastFrameAt = 0;

    let map = null;
    const markers = new Map();

    // ------------------------------------------------------------------ load

    function journeyCodeFromUrl() {
        const params = new URLSearchParams(window.location.search);
        return WayseraCrypto.normaliseCode(params.get('j') || '');
    }

    async function load() {
        const code = journeyCodeFromUrl();
        if (!WayseraCrypto.isValidCode(code)) {
            return fail('That journey code does not look right.');
        }

        journey = await WayseraStore.getJourney(code);
        if (!journey) {
            return fail('No journey with that code is stored on this device.');
        }

        const points = await WayseraStore.getPoints(code);
        events = await WayseraStore.getEvents(code);
        names = WayseraExport.namesFromEvents(events);

        if (points.length === 0) {
            return fail('This journey has no recorded positions yet.');
        }

        tracks = WayseraExport.groupByMember(points);
        startTs = points[0].ts;
        endTs = points[points.length - 1].ts;
        currentTs = startTs;

        renderHeader();
        buildMap(points);
        renderEvents();
        wireControls();
        seek(startTs);
    }

    function fail(message) {
        const host = document.getElementById('replayError');
        host.textContent = message;
        host.style.display = 'block';
        document.getElementById('replayBody').style.display = 'none';
    }

    // ------------------------------------------------------------------ chrome

    function renderHeader() {
        WayseraValidate.setText(
            document.getElementById('replayTitle'),
            journey.destination ? journey.destination.name : `Journey ${journey.code}`
        );

        const minutes = Math.max(1, Math.round((endTs - startTs) / 60000));
        WayseraValidate.setText(
            document.getElementById('replaySubtitle'),
            `${journey.code} · ${tracks.size} ${tracks.size === 1 ? 'person' : 'people'} · ${minutes} min`
        );
    }

    function colourFor(memberId) {
        const palette = ['#4F46E5', '#0EA5E9', '#14B8A6', '#F59E0B', '#EC4899', '#8B5CF6'];
        const hash = Array.from(memberId).reduce((total, ch) => total + ch.charCodeAt(0), 0);
        return palette[hash % palette.length];
    }

    function buildMap(points) {
        map = L.map('replayMap', { preferCanvas: true, zoomSnap: 0.25 });

        // Same basemap as the live map, including the night variant.
        const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const basemap = dark ? 'alidade_smooth_dark' : 'osm_bright';
        const stadiaKey = (window.WAYSERA_CONFIG && window.WAYSERA_CONFIG.STADIA_KEY) || '';
        const keyParam = stadiaKey ? `?api_key=${encodeURIComponent(stadiaKey)}` : '';

        L.tileLayer(`https://tiles.stadiamaps.com/tiles/${basemap}/{z}/{x}/{y}{r}.png${keyParam}`, {
            attribution: '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            detectRetina: true,
            maxZoom: 20
        }).addTo(map);

        for (const [memberId, track] of tracks) {
            L.polyline(track.map((p) => [p.lat, p.lng]), {
                color: colourFor(memberId),
                weight: 4,
                opacity: 0.45
            }).addTo(map);

            const marker = L.circleMarker([track[0].lat, track[0].lng], {
                radius: 8,
                color: '#FFFFFF',
                weight: 2,
                fillColor: colourFor(memberId),
                fillOpacity: 1
            }).addTo(map);

            const label = document.createElement('strong');
            label.textContent = names.get(memberId) || 'Someone';
            marker.bindPopup(label);

            markers.set(memberId, marker);
        }

        if (journey.destination) {
            L.circleMarker([journey.destination.lat, journey.destination.lng], {
                radius: 9,
                color: '#0F766E',
                weight: 3,
                fillColor: '#14B8A6',
                fillOpacity: 0.9
            }).addTo(map);
        }

        map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lng])).pad(0.15));
    }

    function renderEvents() {
        const host = document.getElementById('replayEvents');
        host.replaceChildren();

        if (events.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'replay-empty';
            empty.textContent = 'Nothing was logged during this journey.';
            host.appendChild(empty);
            return;
        }

        for (const event of events) {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'replay-event';
            row.onclick = () => {
                pause();
                seek(event.ts);
            };

            const time = document.createElement('span');
            time.className = 'replay-event-time';
            time.textContent = formatOffset(event.ts - startTs);

            const text = document.createElement('span');
            text.className = 'replay-event-text';
            // textContent: names and messages came from other devices.
            text.textContent = describe(event);

            row.append(time, text);
            host.appendChild(row);
        }
    }

    function describe(event) {
        const data = event.data || {};
        const who = data.name || names.get(data.memberId) || 'Someone';
        if (event.kind === 'joined') return `${who} joined`;
        if (event.kind === 'left') return `${who} left`;
        if (event.kind === 'quick_message') return `${who}: ${data.text || ''}`;
        if (event.kind === 'arrived') return `${who} arrived`;
        return `${who}: ${event.kind}`;
    }

    function formatOffset(ms) {
        const total = Math.max(0, Math.round(ms / 1000));
        const minutes = Math.floor(total / 60);
        const seconds = total % 60;
        return `${minutes}:${String(seconds).padStart(2, '0')}`;
    }

    // --------------------------------------------------------------- playback

    /**
     * Position of one person at an arbitrary moment.
     *
     * Returns null before their first point and holds at their last. People
     * join and leave mid-journey, so a track rarely covers the whole timeline.
     */
    function positionAt(track, ts) {
        if (ts <= track[0].ts) return ts < track[0].ts ? null : track[0];
        const last = track[track.length - 1];
        if (ts >= last.ts) return last;

        let low = 0;
        let high = track.length - 1;
        while (high - low > 1) {
            const mid = (low + high) >> 1;
            if (track[mid].ts <= ts) low = mid;
            else high = mid;
        }

        const before = track[low];
        const after = track[high];
        const span = after.ts - before.ts;
        const ratio = span === 0 ? 0 : (ts - before.ts) / span;

        return {
            lat: before.lat + (after.lat - before.lat) * ratio,
            lng: before.lng + (after.lng - before.lng) * ratio
        };
    }

    function seek(ts) {
        currentTs = Math.min(endTs, Math.max(startTs, ts));

        for (const [memberId, track] of tracks) {
            const marker = markers.get(memberId);
            const position = positionAt(track, currentTs);
            if (!position) {
                // Not on the journey yet. Hide them instead of parking the
                // marker at the origin.
                if (map.hasLayer(marker)) map.removeLayer(marker);
                continue;
            }
            if (!map.hasLayer(marker)) marker.addTo(map);
            marker.setLatLng([position.lat, position.lng]);
        }

        const scrubber = document.getElementById('replayScrubber');
        scrubber.value = String(currentTs - startTs);
        WayseraValidate.setText(
            document.getElementById('replayClock'),
            `${formatOffset(currentTs - startTs)} / ${formatOffset(endTs - startTs)}`
        );
    }

    function frame(now) {
        if (!playing) return;

        const delta = lastFrameAt ? now - lastFrameAt : 0;
        lastFrameAt = now;
        seek(currentTs + delta * speed);

        if (currentTs >= endTs) {
            pause();
            return;
        }
        requestAnimationFrame(frame);
    }

    function play() {
        if (currentTs >= endTs) currentTs = startTs;
        playing = true;
        lastFrameAt = 0;
        WayseraValidate.setText(document.getElementById('replayPlay'), 'Pause');
        requestAnimationFrame(frame);
    }

    function pause() {
        playing = false;
        WayseraValidate.setText(document.getElementById('replayPlay'), 'Play');
    }

    function wireControls() {
        const scrubber = document.getElementById('replayScrubber');
        scrubber.min = '0';
        scrubber.max = String(endTs - startTs);
        scrubber.step = '100';
        scrubber.addEventListener('input', () => {
            pause();
            seek(startTs + Number(scrubber.value));
        });

        document.getElementById('replayPlay').onclick = () => (playing ? pause() : play());

        const speedHost = document.getElementById('replaySpeeds');
        speedHost.replaceChildren();
        for (const option of SPEEDS) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `replay-speed${option === speed ? ' is-active' : ''}`;
            button.textContent = `${option}x`;
            button.onclick = () => {
                speed = option;
                for (const sibling of speedHost.children) {
                    sibling.classList.toggle('is-active', sibling === button);
                }
            };
            speedHost.appendChild(button);
        }

        document.getElementById('replayExportJson').onclick = async () => {
            const points = await WayseraStore.getPoints(journey.code);
            WayseraExport.download(
                `waysera-${journey.code}.json`,
                'application/json',
                WayseraExport.toJSON(journey, points, events)
            );
        };

        document.getElementById('replayExportGpx').onclick = async () => {
            const points = await WayseraStore.getPoints(journey.code);
            WayseraExport.download(
                `waysera-${journey.code}.gpx`,
                'application/gpx+xml',
                WayseraExport.toGPX(journey, points, events)
            );
        };
    }

    window.addEventListener('load', () => {
        // The test page loads this file for its pure helpers; only drive the
        // replay when the replay markup is actually present.
        if (!document.getElementById('replayMap')) return;
        load().catch((error) => fail(`Could not open this journey: ${error.message}`));
    });

    // Exposed for tests.
    window.WayseraReplayInternals = { positionAt };
})();
