package dev.kymorem.android;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = dp(20);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setBackgroundColor(0xff0b1020);

        TextView title = new TextView(this);
        title.setText(getString(R.string.app_name));
        title.setTextColor(0xfff4f7fb);
        title.setTextSize(32);
        title.setGravity(Gravity.START);
        root.addView(title, matchWrap());

        TextView summary = new TextView(this);
        summary.setText(getString(R.string.summary));
        summary.setTextColor(0xffb8c2d6);
        summary.setTextSize(16);
        summary.setPadding(0, dp(10), 0, dp(22));
        root.addView(summary, matchWrap());

        EditText host = field(getString(R.string.host_hint));
        host.setText("127.0.0.1:54865");
        root.addView(host, matchWrap());

        EditText token = field(getString(R.string.token_hint));
        token.setText("kymorem-local-default-change-me");
        root.addView(token, matchWrap());

        Button connect = new Button(this);
        connect.setText(getString(R.string.connect));
        connect.setTextColor(0xff0b1020);
        connect.setBackgroundColor(0xff19d3da);
        root.addView(connect, matchWrap());

        TextView status = new TextView(this);
        status.setText(getString(R.string.mvp_status));
        status.setTextColor(0xff39e58c);
        status.setTextSize(14);
        status.setPadding(0, dp(18), 0, 0);
        root.addView(status, matchWrap());

        connect.setOnClickListener(view -> status.setText(getString(R.string.pairing_placeholder)));
        setContentView(root);
    }

    private EditText field(String hint) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setHintTextColor(0xff6f7b91);
        field.setTextColor(0xfff4f7fb);
        field.setTextSize(16);
        field.setSingleLine(true);
        field.setPadding(dp(14), dp(8), dp(14), dp(8));
        return field;
    }

    private LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 0, 0, dp(12));
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }
}
