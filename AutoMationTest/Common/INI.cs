using System;
using System.Collections.Generic;
//using System.Linq;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;
using AutoMationTest.Robots;
using System.Windows.Forms;

namespace AutoMationTest.Common
{
    public class INI
    {

        [DllImport("Kernel32.dll")]
        public static extern int GetPrivateProfileString([MarshalAs(UnmanagedType.LPStr)] string lpAppName, [MarshalAs(UnmanagedType.LPStr)] string lpKeyName, [MarshalAs(UnmanagedType.LPStr)] string lpDefault, StringBuilder lpReturnedString, int nSize, [MarshalAs(UnmanagedType.LPStr)] string lpFileName);
        [DllImport("Kernel32.dll")]
        public static extern bool WritePrivateProfileString([MarshalAs(UnmanagedType.LPStr)] string lpAppName, [MarshalAs(UnmanagedType.LPStr)] string lpKeyName, [MarshalAs(UnmanagedType.LPStr)] string lpString, [MarshalAs(UnmanagedType.LPStr)] string lpFileName);

        #region Read INI Function
        public static string ReadINI(string FileName, string AppName, string KeyName, string Default)
        {
            return ReadINI(Directory.GetCurrentDirectory(), FileName, AppName, KeyName, Default, 500);
        }

        public static string ReadINI(string FileName, string AppName, string KeyName, string Default, int Length)
        {
            return ReadINI(Directory.GetCurrentDirectory(), FileName, AppName, KeyName, Default, Length);
        }

        public static string ReadINI(string Path, string FileName, string AppName, string KeyName, string Default)
        {
            try
            {
                return ReadINI(Path, FileName, AppName, KeyName, Default, 500);
            }
            catch (Exception)
            {
                return "";
            }
        }

        public static string ReadINI(string Path, string FileName, string AppName, string KeyName, string Default, int Length)
        {
            try
            {
                FileName = Path + @"\" + FileName + ".ini";
                StringBuilder lpReturnedString = new StringBuilder(Length);
                GetPrivateProfileString(AppName, KeyName, Default, lpReturnedString, Length, FileName);
                return lpReturnedString.ToString(0, lpReturnedString.Length);
            }
            catch (Exception)
            {
                //MessageBox.Show("INI 載入異常!!");
                return "";
            }
        }
        #endregion

        public static void WriteINI(string FileName, string AppName, string KeyName, string lpString)
        {
            FileName = Directory.GetCurrentDirectory() + @"\" + FileName + ".ini";
            WritePrivateProfileString(AppName, KeyName, lpString, FileName);
        }

        public static void WriteINI(string FilePath, string FileName, string AppName, string KeyName, string lpString)
        {
            FileName = FilePath + @"\" + FileName + ".ini";
            WritePrivateProfileString(AppName, KeyName, lpString, FileName);
        }

        public struct RobotSettings
        {
            public string IP;
            public int Port;
            public int SystemPort;
            public int UserPort;
            public int UserPort2;
            public string ComPort;
            public int BaudRate;
            public string LoginPassword;
        }



        public static void ReadRobotSetting(Robot.RobotType robotname, ref RobotSettings _robotSetting)
        {
            switch (robotname)
            {
                case Robot.RobotType.Denso:
                    _robotSetting.IP = ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "IP", "");
                    _robotSetting.Port = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "Port", "0"));
                    break;
                case Robot.RobotType.Epson:
                    _robotSetting.IP = ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "IP", "");
                    _robotSetting.SystemPort = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "SystemPort", "0"));
                    _robotSetting.UserPort = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort", "0"));
                    try
                    {
                        _robotSetting.UserPort2 = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort2", ""));
                    }
                    catch (Exception ex)
                    {
                        _robotSetting.UserPort2 = 0;
                    }
                    _robotSetting.LoginPassword = ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "LoginPassword", "");

                    break;
                case Robot.RobotType.TM:
                    _robotSetting.Port = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "TM", "Port", "0"));
                    break;
                case Robot.RobotType.UR:
                    _robotSetting.IP = ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "IP", "");
                    _robotSetting.Port = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "Port", "0"));
                    break;
                case Robot.RobotType.YAMAHA:
                    _robotSetting.ComPort = ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "COM", "");
                    _robotSetting.BaudRate = Convert.ToInt32(ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "BaudRate", "0"));
                    break;
            }
        }

        public static void WriteRobotSetting(Robot.RobotType robotname, RobotSettings _robotSetting)
        {
            switch (robotname)
            {
                case Robot.RobotType.Denso:
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Denso", "IP", _robotSetting.IP);
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Denso", "Port", _robotSetting.Port.ToString());
                    break;
                case Robot.RobotType.Epson:
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "IP", _robotSetting.IP);
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "SystemPort", _robotSetting.SystemPort.ToString());
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort", _robotSetting.UserPort.ToString());
                    if (_robotSetting.UserPort2 != 0)
                    {
                        WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort2", _robotSetting.UserPort2.ToString());
                    }
                    else
                    {
                        WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort2", "");
                    }
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "Epson", "LoginPassword", _robotSetting.LoginPassword);
                    break;
                case Robot.RobotType.TM:
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "TM", "Port", _robotSetting.Port.ToString());
                    break;
                case Robot.RobotType.UR:
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "UR", "IP", _robotSetting.IP);
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "UR", "Port", _robotSetting.Port.ToString());
                    break;
                case Robot.RobotType.YAMAHA:
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "COM", _robotSetting.ComPort);
                    WriteINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "BaudRate", _robotSetting.BaudRate.ToString());
                    break;
            }
        }

    }
}
