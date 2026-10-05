import { useCallback, useEffect, useRef, useState } from 'react';
import { AppLogo } from '@/components/shared/AppLogo';
import { Camera, CheckCircle2, Compass, Loader2, LocateFixed, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react';
import { getCpvCapture, postCpvCapture, submitCpv, type CpvCaptureState, type CpvKind } from '@/services/api';

/**
 * The merchant's shop-verification page (opened from the secure link; mobile first).
 * Camera only: there is no file input and no gallery picker, and every frame is stamped with high-accuracy GPS, compass bearing and the time.
 * A browser cannot PROVE a photo is live, so the server also checks the clock, GPS accuracy, EXIF and that both photos came from the same place.
 */
const STEP_COPY: Record<CpvKind, { title: string; hint: string; facing: 'environment' | 'user' }> = {
  exterior: { title: 'Shop front with the signboard', hint: 'Stand outside, facing the shop, so the full signboard is readable.', facing: 'environment' },
  counter: { title: 'Billing counter or QR stand', hint: 'Show where customers pay: the counter, menu or products, and the QR stand.', facing: 'environment' },
  selfie: { title: 'Owner selfie (for the video KYC)', hint: 'Optional now. A clear photo of your face helps the video KYC step.', facing: 'user' },
};

interface Fix { lat: number; lon: number; accuracy: number }

function accuracyTone(acc: number, max: number) {
  return acc <= max ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-amber-800 bg-amber-50 border-amber-200';
}

export function CpvCapturePage({ token }: { token: string }) {
  const [state, setState] = useState<CpvCaptureState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [fix, setFix] = useState<Fix | null>(null);
  const [heading, setHeading] = useState<number | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [camError, setCamError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thumbs, setThumbs] = useState<Partial<Record<CpvKind, string>>>({});
  const [captured, setCaptured] = useState<Set<CpvKind>>(new Set());
  const [submitted, setSubmitted] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const watchRef = useRef<number | null>(null);

  const steps: CpvKind[] = state ? [...state.required, ...state.optional] : [];
  const kind = steps[stepIndex];
  const secure = typeof window !== 'undefined' ? window.isSecureContext : true;
  const max = state?.maxAccuracyM ?? 100;
  const goodFix = !!fix && fix.accuracy <= max;
  const requiredDone = !!state && state.required.every((k) => captured.has(k));

  useEffect(() => {
    getCpvCapture(token).then((s) => {
      setState(s);
      setCaptured(new Set(Object.keys(s.captured) as CpvKind[]));
      if (s.status !== 'waiting') setSubmitted(true);
    }, (e) => setLoadError(e instanceof Error ? e.message.replace(/^\d{3}\s/, '') : String(e)));
  }, [token]);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startCamera = useCallback(async (facing: 'environment' | 'user') => {
    stopCamera();
    setCamError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCamError('This browser cannot open the camera. Open the link in Chrome or Safari on your phone.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
    } catch (e) {
      setCamError(e instanceof Error && e.name === 'NotAllowedError' ? 'Camera access was blocked. Allow the camera for this page and try again.' : 'The camera could not be opened.');
    }
  }, [stopCamera]);

  const startSensors = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError('This browser has no location access.');
      return;
    }
    watchRef.current = navigator.geolocation.watchPosition(
      (p) => { setGeoError(null); setFix({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }); },
      (e) => setGeoError(e.code === 1 ? 'Location access was blocked. Allow precise location for this page and try again.' : 'Could not get your location yet. Step outside or near a window.'),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 },
    );
    const onOrient = (ev: DeviceOrientationEvent) => {
      const compass = (ev as unknown as { webkitCompassHeading?: number }).webkitCompassHeading;
      if (typeof compass === 'number') setHeading(compass);
      else if (ev.alpha !== null && ev.alpha !== undefined) setHeading((360 - ev.alpha) % 360);
    };
    const DOE = window.DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> } | undefined;
    const attach = () => {
      window.addEventListener('deviceorientationabsolute' as 'deviceorientation', onOrient, true);   // Android: true compass heading
      window.addEventListener('deviceorientation', onOrient, true);                                   // iOS: webkitCompassHeading
    };
    if (DOE?.requestPermission) void DOE.requestPermission().then((r) => { if (r === 'granted') attach(); }).catch(() => undefined);
    else attach();
  }, []);

  useEffect(() => () => {
    stopCamera();
    if (watchRef.current !== null) navigator.geolocation?.clearWatch(watchRef.current);
  }, [stopCamera]);

  useEffect(() => {
    if (started && kind && !submitted) void startCamera(STEP_COPY[kind].facing);
  }, [started, kind, submitted, startCamera]);

  const begin = () => { setStarted(true); startSensors(); };

  const capture = async () => {
    const video = videoRef.current;
    if (!video || !kind || !fix) return;
    setBusy(true);
    setError(null);
    try {
      const scale = Math.min(1, 1600 / Math.max(video.videoWidth || 1600, 1));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round((video.videoWidth || 1280) * scale);
      canvas.height = Math.round((video.videoHeight || 960) * scale);
      canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.9));
      if (!blob) throw new Error('The photo could not be taken. Try again.');
      await postCpvCapture(token, blob, { kind, lat: fix.lat, lon: fix.lon, accuracyM: fix.accuracy, heading });
      setThumbs((t) => ({ ...t, [kind]: URL.createObjectURL(blob) }));
      setCaptured((c) => new Set(c).add(kind));
      if (stepIndex < steps.length - 1) setStepIndex(stepIndex + 1);
    } catch (e) {
      setError((e instanceof Error ? e.message : String(e)).replace(/^\d{3}\s/, ''));
    } finally {
      setBusy(false);
    }
  };

  // DEMO ONLY (the server allows it only with CPV_ALLOW_DEMO_REFERENCE=true): use a picture file instead of the camera.
  const uploadFile = async (file: File | undefined) => {
    if (!file || !kind || !fix) return;
    setBusy(true);
    setError(null);
    try {
      await postCpvCapture(token, file, { kind, lat: fix.lat, lon: fix.lon, accuracyM: fix.accuracy, heading, source: 'demo_upload' });
      setThumbs((t) => ({ ...t, [kind]: URL.createObjectURL(file) }));
      setCaptured((c) => new Set(c).add(kind));
      if (stepIndex < steps.length - 1) setStepIndex(stepIndex + 1);
    } catch (e) {
      setError((e instanceof Error ? e.message : String(e)).replace(/^\d{3}\s/, ''));
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await submitCpv(token);
      stopCamera();
      setSubmitted(true);
    } catch (e) {
      setError((e instanceof Error ? e.message : String(e)).replace(/^\d{3}\s/, ''));
    } finally {
      setBusy(false);
    }
  };

  // after submitting, follow the verdict
  useEffect(() => {
    if (!submitted || state?.verdict) return;
    let tries = 0;
    const id = window.setInterval(() => {
      tries += 1;
      getCpvCapture(token).then((s) => { setState(s); if (s.verdict || tries > 60) window.clearInterval(id); }, () => undefined);
    }, 4000);
    return () => window.clearInterval(id);
  }, [submitted, state?.verdict, token]);

  // ------------------------------------------------------------------ render
  const shell = (body: React.ReactNode) => (
    <main className="min-h-screen bg-slate-50 text-slate-900 px-4 py-5 flex justify-center">
      <div className="w-full max-w-md space-y-4">
        <header className="flex items-center gap-3">
          <AppLogo suffix="·Drishti" subtitle="Shop verification" />
        </header>
        {body}
      </div>
    </main>
  );

  if (loadError) {
    return shell(<div role="alert" className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-sm text-rose-800 font-semibold">{loadError}</div>);
  }
  if (!state) return shell(<div className="text-sm text-slate-500 flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Opening your verification…</div>);

  if (submitted) {
    const done = state.verdict === 'CPV_VERIFIED';
    const review = state.verdict === 'NEEDS_REVIEW';
    return shell(
      <section className="p-5 rounded-2xl bg-white border border-slate-200 space-y-3 text-center">
        {done ? <CheckCircle2 size={40} className="mx-auto text-emerald-600" /> : review ? <ShieldCheck size={40} className="mx-auto text-amber-600" /> : <Loader2 size={36} className="mx-auto animate-spin text-[#00BAF2]" />}
        <h1 className="text-lg font-extrabold">{done ? 'Your shop is verified' : review ? 'Sent to your account manager' : 'Checking your photos…'}</h1>
        <p className="text-sm text-slate-600">
          {done ? 'Thank you. We will contact you for the next step.'
            : review ? 'A person will look at your photos and get back to you. You do not need to do anything now.'
              : 'This usually takes under a minute. You can keep this page open.'}
        </p>
      </section>,
    );
  }

  if (!started) {
    return shell(
      <section className="p-5 rounded-2xl bg-white border border-slate-200 space-y-4">
        <h1 className="text-lg font-extrabold">Verify {state.merchantName}</h1>
        <p className="text-sm text-slate-600">Take two live photos of your shop. This replaces a visit by a field agent.</p>
        <ol className="text-sm text-slate-700 space-y-1.5 list-decimal pl-5">
          {steps.map((k) => <li key={k}>{STEP_COPY[k].title}{state.optional.includes(k) ? ' (optional)' : ''}</li>)}
        </ol>
        <ul className="text-xs text-slate-500 space-y-1">
          <li>Stand at your shop. Your location is recorded with each photo.</li>
          <li>Photos must be taken now with the camera. Gallery uploads are not accepted.</li>
        </ul>
        {!secure && <div role="alert" className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 font-semibold">This page is not on a secure (https) address, so the phone will not allow the camera or location. Ask your account manager for a secure link.</div>}
        <button onClick={begin} className="w-full py-3 rounded-xl bg-[#002970] text-white font-bold text-sm flex items-center justify-center gap-2">
          <Camera size={16} /> Start verification
        </button>
      </section>,
    );
  }

  return shell(
    <>
      <section className="p-4 rounded-2xl bg-white border border-slate-200 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">Step {stepIndex + 1} of {steps.length}</span>
          {state.optional.includes(kind) && <span className="text-[10px] font-bold text-slate-500 bg-slate-100 rounded px-1.5">optional</span>}
        </div>
        <h2 className="text-base font-extrabold">{STEP_COPY[kind].title}</h2>
        <p className="text-xs text-slate-600">{STEP_COPY[kind].hint}</p>

        <div className="relative rounded-xl overflow-hidden bg-black aspect-[4/3]">
          <video ref={videoRef} playsInline muted autoPlay className="w-full h-full object-cover" data-testid="camera-preview" />
          {camError && <div role="alert" className="absolute inset-0 p-4 flex items-center justify-center text-center text-xs text-white bg-black/70 font-semibold">{camError}</div>}
        </div>

        <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
          <span className={`px-2 py-1 rounded-lg border inline-flex items-center gap-1.5 ${fix ? accuracyTone(fix.accuracy, max) : 'text-slate-600 bg-slate-50 border-slate-200'}`}>
            <LocateFixed size={12} />{fix ? `GPS accuracy ${Math.round(fix.accuracy)} m` : 'Getting your location…'}
          </span>
          <span className="px-2 py-1 rounded-lg border text-slate-600 bg-slate-50 border-slate-200 inline-flex items-center gap-1.5"><Compass size={12} />{heading === null ? 'Bearing unavailable' : `Facing ${Math.round(heading)}°`}</span>
        </div>
        {fix && !goodFix && <p className="text-[11px] text-amber-800 font-semibold">Waiting for a more precise location (need {max} m or better). Step outside or near a window and wait a moment.</p>}
        {geoError && <p role="alert" className="text-[11px] text-rose-700 font-semibold">{geoError}</p>}
        {error && <p role="alert" className="text-xs text-rose-700 font-semibold">{error}</p>}

        <button onClick={() => void capture()} disabled={busy || !goodFix || !!camError}
          className="w-full py-3 rounded-xl bg-[#00BAF2] text-[#002970] font-extrabold text-sm flex items-center justify-center gap-2 disabled:opacity-50">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Camera size={16} />}
          {busy ? 'Uploading…' : captured.has(kind) ? 'Retake photo' : 'Take photo'}
        </button>
        {state.demoUpload && (
          <label className="block text-center text-[11px] font-bold text-slate-600 border border-dashed border-slate-300 rounded-xl py-2 cursor-pointer hover:bg-slate-50">
            Demo only: upload a picture instead
            <input type="file" accept="image/jpeg" className="sr-only" aria-label="Demo only: upload a picture instead" disabled={busy || !goodFix}
              onChange={(e) => { void uploadFile(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
        )}
      </section>

      <section className="grid grid-cols-3 gap-2">
        {steps.map((k, i) => (
          <button key={k} onClick={() => setStepIndex(i)} className={`rounded-xl border p-1.5 text-left ${i === stepIndex ? 'border-[#00BAF2] bg-[#e6f7fc]' : 'border-slate-200 bg-white'}`}>
            <div className="aspect-[4/3] rounded-lg bg-slate-100 overflow-hidden flex items-center justify-center">
              {thumbs[k] ? <img src={thumbs[k]} alt={`${k} photo`} className="w-full h-full object-cover" /> : captured.has(k) ? <CheckCircle2 size={18} className="text-emerald-600" /> : <Camera size={16} className="text-slate-400" />}
            </div>
            <span className="block mt-1 text-[10px] font-bold capitalize text-slate-600">{k}</span>
          </button>
        ))}
      </section>

      {requiredDone && (
        <button onClick={() => void send()} disabled={busy} className="w-full py-3 rounded-xl bg-[#002970] text-white font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-60">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />} Send for verification
        </button>
      )}
      <p className="text-[11px] text-slate-500 flex items-start gap-1.5"><TriangleAlert size={12} className="mt-0.5 shrink-0" />Photos taken earlier or from the gallery cannot be sent.</p>
    </>,
  );
}
