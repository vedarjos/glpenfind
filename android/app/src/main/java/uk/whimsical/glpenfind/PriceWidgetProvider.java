package uk.whimsical.glpenfind;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Home-screen widget: the cheapest published price at the dose the user picked.
 *
 * This is the app's native surface. It reads the price index that ships inside the
 * APK, so it works with no network, no account and no WebView — which is precisely
 * what a "wrapper around a website" cannot do (F-Droid Inclusion Policy, Quality
 * Control 3; Apple guideline 4.2).
 *
 * The index is regenerated with the web build, so a widget refresh only re-reads a
 * bundled asset; it never touches the network.
 */
public class PriceWidgetProvider extends AppWidgetProvider {

    public static final String PREFS = "glpenfind_widget";
    public static final String ACTION_REFRESH = "uk.whimsical.glpenfind.WIDGET_REFRESH";
    public static final String DEFAULT_DOSE = "7.5";
    public static final String[] DOSES = {"2.5", "5", "7.5", "10", "12.5", "15"};

    /** Index path inside the APK — Capacitor copies www/ to assets/public/. */
    private static final String INDEX_ASSET = "public/data/price-index.json";

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] appWidgetIds) {
        for (int id : appWidgetIds) {
            render(context, manager, id);
        }
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        if (ACTION_REFRESH.equals(intent.getAction())) {
            AppWidgetManager manager = AppWidgetManager.getInstance(context);
            int[] ids = manager.getAppWidgetIds(new ComponentName(context, PriceWidgetProvider.class));
            for (int id : ids) {
                render(context, manager, id);
            }
        }
    }

    @Override
    public void onDeleted(Context context, int[] appWidgetIds) {
        SharedPreferences.Editor editor =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        for (int id : appWidgetIds) {
            editor.remove(key(id));
        }
        editor.apply();
    }

    static String key(int widgetId) {
        return "dose_" + widgetId;
    }

    static String doseFor(Context context, int widgetId) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(key(widgetId), DEFAULT_DOSE);
    }

    static void saveDose(Context context, int widgetId, String dose) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(key(widgetId), dose).apply();
    }

    /** Renders one widget instance. Public so the config activity can reuse it. */
    static void render(Context context, AppWidgetManager manager, int widgetId) {
        String dose = doseFor(context, widgetId);
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_price);

        views.setTextViewText(R.id.widget_dose, dose + "mg");

        Best best = cheapestForDose(context, dose);
        if (best == null) {
            views.setTextViewText(R.id.widget_price, "—");
            views.setTextViewText(R.id.widget_pharmacy, "No price published");
            views.setTextViewText(R.id.widget_meta, "open the app for the full list");
        } else {
            views.setTextViewText(R.id.widget_price, money(best.price));
            views.setTextViewText(R.id.widget_pharmacy, best.pharmacy);
            views.setTextViewText(R.id.widget_meta,
                    "cheapest of " + best.pricedCount + " · read " + shortDate(best.readAt));
        }

        // Tap the body to open the app.
        Intent open = new Intent(context, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        views.setOnClickPendingIntent(R.id.widget_root, PendingIntent.getActivity(
                context, widgetId, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));

        // Tap the arrow to re-read the bundled index.
        Intent refresh = new Intent(context, PriceWidgetProvider.class).setAction(ACTION_REFRESH);
        views.setOnClickPendingIntent(R.id.widget_refresh, PendingIntent.getBroadcast(
                context, 1000 + widgetId, refresh,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));

        manager.updateAppWidget(widgetId, views);
    }

    /** Cheapest priced provider at one dose, with the count of providers that publish it. */
    static Best cheapestForDose(Context context, String dose) {
        try (InputStream in = context.getAssets().open(INDEX_ASSET)) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[8192];
            int read;
            while ((read = in.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            JSONObject root = new JSONObject(buffer.toString(StandardCharsets.UTF_8.name()));
            JSONArray providers = root.optJSONArray("providers");
            if (providers == null) {
                return null;
            }

            Best best = null;
            int priced = 0;

            for (int i = 0; i < providers.length(); i++) {
                JSONObject provider = providers.optJSONObject(i);
                if (provider == null) {
                    continue;
                }
                JSONObject prices = provider.optJSONObject("prices_gbp");
                if (prices == null || !prices.has(dose)) {
                    continue;
                }
                double value = prices.optDouble(dose, -1);
                if (value <= 0) {
                    continue;
                }
                priced++;
                if (best == null || value < best.price) {
                    best = new Best(value,
                            provider.optString("provider", ""),
                            provider.optString("retrieved_at", ""));
                }
            }
            if (best != null) {
                best.pricedCount = priced;
            }
            return best;
        } catch (Exception e) {
            return null;
        }
    }

    /** £145 rather than £145.00, but £98.99 keeps its pence. */
    static String money(double value) {
        if (Math.abs(value - Math.rint(value)) < 0.005) {
            return "£" + Math.round(value);
        }
        return String.format(java.util.Locale.UK, "£%.2f", value);
    }

    /** "2026-10-25T19:21:18+00:00" → "25 Oct". */
    static String shortDate(String iso) {
        if (iso == null || iso.length() < 10) {
            return "—";
        }
        String[] months = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
        try {
            int month = Integer.parseInt(iso.substring(5, 7));
            int day = Integer.parseInt(iso.substring(8, 10));
            return day + " " + months[month - 1];
        } catch (Exception e) {
            return "—";
        }
    }

    static final class Best {
        final double price;
        final String pharmacy;
        final String readAt;
        int pricedCount;

        Best(double price, String pharmacy, String readAt) {
            this.price = price;
            this.pharmacy = pharmacy;
            this.readAt = readAt;
        }
    }
}
