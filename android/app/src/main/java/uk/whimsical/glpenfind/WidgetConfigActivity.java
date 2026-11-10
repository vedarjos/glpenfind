package uk.whimsical.glpenfind;

import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.Toast;

/**
 * Shown when the widget is placed: pick the dose the widget should watch.
 *
 * Android requires a configure activity to set RESULT_CANCELED up front, otherwise
 * a dismissed dialog leaves a broken widget on the home screen.
 */
public class WidgetConfigActivity extends Activity {

    private int widgetId = AppWidgetManager.INVALID_APPWIDGET_ID;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Cancel by default: if the user backs out, the widget is not added.
        setResult(RESULT_CANCELED);
        setContentView(R.layout.activity_widget_config);

        Bundle extras = getIntent().getExtras();
        if (extras != null) {
            widgetId = extras.getInt(AppWidgetManager.EXTRA_APPWIDGET_ID,
                    AppWidgetManager.INVALID_APPWIDGET_ID);
        }
        if (widgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish();
            return;
        }

        RadioGroup group = findViewById(R.id.dose_group);
        String current = PriceWidgetProvider.doseFor(this, widgetId);
        int[] buttons = {R.id.dose_2_5, R.id.dose_5, R.id.dose_7_5,
                R.id.dose_10, R.id.dose_12_5, R.id.dose_15};
        for (int i = 0; i < PriceWidgetProvider.DOSES.length; i++) {
            if (PriceWidgetProvider.DOSES[i].equals(current)) {
                ((RadioButton) findViewById(buttons[i])).setChecked(true);
            }
        }

        findViewById(R.id.save).setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                save(group, buttons);
            }
        });
    }

    private void save(RadioGroup group, int[] buttons) {
        int checked = group.getCheckedRadioButtonId();
        String dose = PriceWidgetProvider.DEFAULT_DOSE;
        for (int i = 0; i < buttons.length; i++) {
            if (buttons[i] == checked) {
                dose = PriceWidgetProvider.DOSES[i];
            }
        }

        PriceWidgetProvider.saveDose(this, widgetId, dose);

        AppWidgetManager manager = AppWidgetManager.getInstance(this);
        PriceWidgetProvider.render(this, manager, widgetId);

        PriceWidgetProvider.Best best = PriceWidgetProvider.cheapestForDose(this, dose);
        if (best == null) {
            Toast.makeText(this, "No " + dose + "mg price published yet",
                    Toast.LENGTH_SHORT).show();
        }

        Intent result = new Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId);
        setResult(RESULT_OK, result);
        finish();
    }
}
