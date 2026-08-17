package @RENDERDOC_ANDROID_PACKAGE_NAME@;
import android.os.Build;
import android.app.Activity;
import android.view.WindowManager;
import android.os.Environment;
import android.content.Intent;

public class Loader extends android.app.NativeActivity
{
    /* load our native library */
    static {
        System.loadLibrary("renderdoccmd"); // this will load VkLayer_GLES_RenderDoc as well
    }

    @Override
    protected void onCreate(android.os.Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        // MIUI/Android 13+ permission requests hang or fail, skip them.
        // Server works with app-private directory without MANAGE_EXTERNAL_STORAGE.
    }
}
