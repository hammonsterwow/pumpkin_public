import { registerRootComponent } from 'expo';

import App from './App';
import FaceEnrollmentDemoApp from './FaceEnrollmentDemoApp';

// Normal customer app (including Firebase authentication) is the default.
// Set EXPO_PUBLIC_FACE_ENROLLMENT_DEMO=1 only when the standalone
// face-enrollment test screen is intentionally needed.
const RootComponent =
  process.env.EXPO_PUBLIC_FACE_ENROLLMENT_DEMO === '1'
    ? FaceEnrollmentDemoApp
    : App;

registerRootComponent(RootComponent);
