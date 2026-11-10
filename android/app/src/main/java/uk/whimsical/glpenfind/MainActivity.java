package uk.whimsical.glpenfind;

import android.content.Intent;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

/**
 * Capacitor host. Extended only so launcher shortcuts can open a specific page:
 * a shortcut carries a "route" extra (e.g. prices.html) and the WebView is pointed
 * at that path on the local origin instead of index.html.
 */
public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        route(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        route(intent);
    }

    private void route(Intent intent) {
        if (intent == null) {
            return;
        }
        final String path = intent.getStringExtra("route");
        if (path == null || getBridge() == null || getBridge().getWebView() == null) {
            return;
        }
        if (!path.matches("[a-z0-9-]+\\.html")) {
            return;
        }
        getBridge().getWebView().post(new Runnable() {
            @Override
            public void run() {
                getBridge().getWebView().loadUrl("https://localhost/" + path);
            }
        });
    }
}
