import subprocess
import time
import pyvjoy
import re

VJOY_AXIS_MAX = 32768

dormant_values = None
vjoy_device = pyvjoy.VJoyDevice(1)

def scale_axis_value(value, min_value=359, max_value=1689):
    value = max(min_value, min(max_value, value))
    normalized = (value - min_value) / (max_value - min_value)
    return int(normalized * VJOY_AXIS_MAX)

def negate_values(value, min_value=359, max_value=1689):
    return max_value + min_value - value

def extract_joystick_values(line):
    match_lh = re.search(r'leftHorizontalValue:\s*(\d+)', line)
    match_lv = re.search(r'leftVerticalValue:\s*(\d+)', line)
    match_rh = re.search(r'rightHorizontalValue:\s*(\d+)', line)
    match_rv = re.search(r'rightVerticalValue:\s*(\d+)', line)
    match_w1 = re.search(r'wheelValue1:\s*(\d+)', line)
    match_w2 = re.search(r'thumbWheelValue:\s*(\d+)', line)
    match_bt = re.search(r'buttonType:\s*(\w+)', line)

    if any([match_lh, match_lv, match_rh, match_rv, match_w1, match_w2, match_bt]):
        return {
            'left_horizontal': int(match_lh.group(1)) if match_lh else None,
            'left_vertical': int(match_lv.group(1)) if match_lv else None,
            'right_horizontal': int(match_rh.group(1)) if match_rh else None,
            'right_vertical': int(match_rv.group(1)) if match_rv else None,
            'wheel1': int(match_w1.group(1)) if match_w1 else None,
            'thumbWheelValue': int(match_w2.group(1)) if match_w2 else None,
            'button_type': match_bt.group(1) if match_bt else None
        }
    return None

def send_input_to_vjoy(values):
    print(values)
    try:
        if values.get('left_horizontal') is not None:
            vjoy_device.data.wAxisX = scale_axis_value(values['left_horizontal'])
        if values.get('left_vertical') is not None:
            vjoy_device.data.wAxisY = scale_axis_value(values['left_vertical'])
        if values.get('right_horizontal') is not None:
            vjoy_device.data.wAxisXRot = scale_axis_value(negate_values(values['right_horizontal']))
        if values.get('right_vertical') is not None:
            vjoy_device.data.wAxisYRot = scale_axis_value(negate_values(values['right_vertical']))
        if values.get('wheel1') is not None:
            vjoy_device.data.wAxisZ = scale_axis_value(values['wheel1'], 724, 1324)

        btn_type = values.get('button_type')
        thumb_val = values.get('thumbWheelValue')

        if thumb_val is not None and btn_type in ["ZOOM_IN", "ZOOM_OUT"]:
            combined_val = thumb_val if btn_type == "ZOOM_IN" else -thumb_val
            vjoy_device.data.wAxisZRot = int(((combined_val + 255) / 510) * VJOY_AXIS_MAX)
        elif btn_type:
            for i in range(1, 5):
                vjoy_device.set_button(i, 0)
            if btn_type == "UNKNOWN":
                vjoy_device.set_button(1, 1)
            elif btn_type == "RIGHT_CUSTOM":
                vjoy_device.set_button(1, 1)
            elif btn_type == "LEFT_CUSTOM":
                vjoy_device.set_button(2, 1)
            else:
                print(f"Unmapped button: {btn_type}")

        vjoy_device.update()
    except Exception as e:
        print("vJoy error:", e)

def stream_logcat():
    global dormant_values
    process = subprocess.Popen(
        ['adb', 'logcat', '-v', 'time'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace'
    )

    last_values = {}
    try:
        for line in process.stdout:
            values = extract_joystick_values(line)
            if values:
                for key, val in values.items():
                    if val is not None:
                        last_values[key] = val
                send_input_to_vjoy(last_values)
                dormant_values = last_values
            elif dormant_values:
                  send_input_to_vjoy(dormant_values)
    except KeyboardInterrupt:
        print("Stopping...")
        process.terminate()
    except Exception as e:
        print(f"Error reading logcat: {e}")
        process.terminate()

if __name__ == "__main__":
    print("Starting real-time logcat → vJoy bridge...")
    print("Press Ctrl+C to stop.")
    stream_logcat()