using System.Collections;
using System.Collections.Generic;
//using UnityEngine;
using System.Runtime.InteropServices;
using System;
namespace AutoMationTest.Device
{
    public static class JoyStickHelper
    {
        public static JoyStickInfo infoEx = new JoyStickInfo();
        public static int ButtonState;
        public static int ButtonUpState;
        public static int ButtonDownState;
        public static int[] AxisState = new int[6];
        public enum JoyStickButtonCode
        {
            Button01 = 0x1,
            Button02 = 0x2,
            Button03 = 0x4,
            Button04 = 0x8,
            Button05 = 0x10,
            Button06 = 0x20,
            Button07 = 0x40,
            Button08 = 0x80,
            Button09 = 0x100,
            Button10 = 0x200,
            Button11 = 0x400,
            Button12 = 0x800,
            Button13 = 0x1000,
            Button14 = 0x2000,
            Button15 = 0x4000,
            Button16 = 0x8000,
            Button17 = 0x10000,
            Button18 = 0x20000,
            Button19 = 0x40000,
            Button20 = 0x80000,
            Button21 = 0x100000,
            Button22 = 0x200000,
            Button23 = 0x400000,
            Button24 = 0x800000,
            Button25 = 0x1000000,
            Button26 = 0x2000000,
            Button27 = 0x4000000,
            Button28 = 0x8000000,
            Button29 = 0x10000000,
            Button30 = 0x20000000,
            Button31 = 0x40000000,
            //Button32 = -0x80000000,
            none = -1
        }
        public enum ControlDirection
        {
            X = 0,
            Y = 1,
            Z = 2,
            U = 3,
            V = 4,
            R = 5
        }
        [DllImport("winmm")]
        private static extern int joyGetPosEx(int uJoyID, ref JoyStickInfo pji);
        public static int UpdateInfoEx()
        {
            if (infoEx.dwSize == 0)
            {
                infoEx.dwSize = Marshal.SizeOf(typeof(JoyStickInfo));
                infoEx.dwFlags = 0x00000080;
            }
            int beforeBtnState = ButtonState;
            int result = joyGetPosEx(0, ref infoEx);
            ButtonState = infoEx.dwButtons;
            ButtonUpState = beforeBtnState & (beforeBtnState ^ ButtonState);
            ButtonDownState = (~beforeBtnState) & (beforeBtnState ^ ButtonState);
            AxisState[0] = infoEx.dwXpos;
            AxisState[1] = infoEx.dwYpos;
            AxisState[2] = infoEx.dwZpos;
            AxisState[3] = infoEx.dwUpos;
            AxisState[4] = infoEx.dwVpos;
            AxisState[5] = infoEx.dwRpos;
            return result;
        }
        public static int GetAxisPosition(ControlDirection axis)
        {
            return AxisState[Convert.ToInt32(axis)];
        }
        public static bool GetButton(JoyStickButtonCode code)
        {
            if (code == JoyStickButtonCode.none)
                return false;
            string buttonName = Enum.GetName(typeof(JoyStickButtonCode), code);
            int index = int.Parse(buttonName.Substring(buttonName.Length - 2));
            int mask = 1 << (index - 1);
            return (ButtonState & mask) > 0;
        }
        public static bool GetUpButton(JoyStickButtonCode code)
        {
            if (code == JoyStickButtonCode.none)
                return false;
            string buttonName = Enum.GetName(typeof(JoyStickButtonCode), code);
            int index = int.Parse(buttonName.Substring(buttonName.Length - 2));
            int mask = 1 << (index - 1);
            return (ButtonUpState & mask) > 0;
        }
        public static bool GetDownButton(JoyStickButtonCode code)
        {
            if (code == JoyStickButtonCode.none)
                return false;
            string buttonName = Enum.GetName(typeof(JoyStickButtonCode), code);
            int index = int.Parse(buttonName.Substring(buttonName.Length - 2));
            int mask = 1 << (index - 1);
            return (ButtonDownState & mask) > 0;
        }
        public struct JoyStickInfo
        {
            public int dwSize;
            public int dwFlags;
            public int dwXpos;
            public int dwYpos;
            public int dwZpos;
            public int dwRpos;
            public int dwUpos;
            public int dwVpos;
            public int dwButtons;
            public int dwButtonNumber;
            public int dwPOV;
            public int dwReserved1;
            public int dwReserved2;
        }
    }
}
