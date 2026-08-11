import { useCallback, useEffect, useRef } from 'react';
import { useTheme } from '../../lms/theme';

export default function FieldOperatorScreen() {
  const { theme } = useTheme();
  const frameRef = useRef<HTMLIFrameElement | null>(null);

  // Theme is passed both in the URL (correct initial load) and via postMessage
  // (live switching without reloading the 3D scene).
  const src = `/avt4_3d_model_v7.html?theme=${theme}`;

  const syncTheme = useCallback(() => {
    const frame = frameRef.current;
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage({ type: 'elou-theme', theme }, '*');
    }
  }, [theme]);

  useEffect(() => {
    syncTheme();
  }, [syncTheme]);

  return (
    <div className="field-operator-screen">
      <iframe
        ref={frameRef}
        src={src}
        onLoad={syncTheme}
        title="Экран полевого оператора — 3D-модель установки"
        className="field-operator-frame"
      />
    </div>
  );
}
