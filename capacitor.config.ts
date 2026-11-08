import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'uk.whimsical.glpenfind',
  appName: 'GLPenFind',
  webDir: 'www',
  server: { androidScheme: 'https' },
  plugins: {
    SplashScreen: { launchShowDuration: 700, backgroundColor: '#a7d4e4' },
  },
};

export default config;
