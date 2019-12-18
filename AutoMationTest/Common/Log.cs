using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.IO;
using System.Threading;
//using 

namespace AutoMationTest.Common
{
    public class Log
    {

        private static string Main_LogPath = "";
        private static string Main_Log = "";
        private static string DUT_LogPath = "";
        private static string DUT_Log = "";
        private static string Exception_LogPath = "";
        private static string Exception_Log = "";
        private static string NG_LogPath = "";
        private static string NG_Log = "";
        private static string Warn_LogPath = "";
        private static string Warn_Log = "";
        private static string RobotError_LogPath = "";
        private static string RobotError_Log = "";
        private static string Manual_LogPath = "";
        private static string Manual_Log = "";


        public enum TestResult
        {
            Pass,
            NG,
            Warning,
            Exception,
            RobotError,
            Retest
        }



        public static void CreatDirectory()
        {
            Main_LogPath = Application.StartupPath + "\\Log\\Main";
            if (!Directory.Exists(Main_LogPath))
            {
                Directory.CreateDirectory(Main_LogPath);
            }

            DUT_LogPath = Application.StartupPath + "\\Log\\DUT";
            if (!Directory.Exists(DUT_LogPath))
            {
                Directory.CreateDirectory(DUT_LogPath);
            }

            NG_LogPath = Application.StartupPath + "\\Log\\NG";
            if (!Directory.Exists(NG_LogPath))
            {
                Directory.CreateDirectory(NG_LogPath);
            }

            Warn_LogPath = Application.StartupPath + "\\Log\\Warning";
            if (!Directory.Exists(Warn_LogPath))
            {
                Directory.CreateDirectory(Warn_LogPath);
            }

            Exception_LogPath = Application.StartupPath + "\\Log\\Exception";
            if (!Directory.Exists(Exception_LogPath))
            {
                Directory.CreateDirectory(Exception_LogPath);
            }

            RobotError_LogPath = Application.StartupPath + "\\Log\\RobotError";
            if (!Directory.Exists(RobotError_LogPath))
            {
                Directory.CreateDirectory(RobotError_LogPath);
            }

            Manual_LogPath = Application.StartupPath + "\\Log\\Manual";
            if (!Directory.Exists(Manual_LogPath))
            {
                Directory.CreateDirectory(Manual_LogPath);
            }
        }

        public static void AddMainLog(string text)
        {

            CreatDirectory();

            try
            {
                if (!Main_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    Main_Log = Main_LogPath + "\\MainLog_" + DateTime.Now.ToString("yyyyMMdd") + ".txt";
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss.fff ");
                text = nowTime + "  " + text + "\r\n";

                File.AppendAllText(Main_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddAllDUTLog(string SN, TestResult Result)
        {

            CreatDirectory();

            try
            {
                if (!DUT_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    DUT_Log = DUT_LogPath + "\\AllDUT_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    File.AppendAllText(DUT_Log, "時間,SN,測試結果\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + Result.ToString() + "\r\n";

                File.AppendAllText(DUT_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddAllDUTLog(string SN, TestResult Result, int FixtureNum)
        {

            CreatDirectory();

            try
            {
                if (!DUT_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    DUT_Log = DUT_LogPath + "\\" + Produce.Station.Name[FixtureNum].ToString() + "_All_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(DUT_Log))
                        File.AppendAllText(DUT_Log, "時間,SN,測試結果,治具\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + Result.ToString() + "," + FixtureNum.ToString() + "\r\n";

                File.AppendAllText(DUT_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddNGLog(string SN, string NGItem, string NGData)
        {

            CreatDirectory();

            try
            {
                if (!NG_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    NG_Log = NG_LogPath + "\\NG_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(NG_Log))
                        File.AppendAllText(NG_Log, "時間,SN,NG測項,測試值\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + NGItem + "," + NGData + "\r\n";

                File.AppendAllText(NG_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddNGLog(string SN, string NGItem, string NGData, int FixtureNum)
        {

            CreatDirectory();

            try
            {
                if (!NG_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    NG_Log = NG_LogPath + "\\" + Produce.Station.Name[FixtureNum].ToString() + "_NG_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(NG_Log))
                        File.AppendAllText(NG_Log, "時間,SN,NG測項,測試值,治具\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + NGItem + "," + NGData + "," + FixtureNum.ToString() + "\r\n";

                File.AppendAllText(NG_Log, text);
            }
            catch (Exception ex)
            {

            }

        }


        public static void AddWarningLog(string SN, string WarningMsg)
        {
            CreatDirectory();

            try
            {
                if (!Warn_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    Warn_Log = Warn_LogPath + "\\Warn_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(Warn_Log))
                        File.AppendAllText(Warn_Log, "時間,SN,警告信息\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + WarningMsg + "\r\n";

                File.AppendAllText(Warn_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddWarningLog(string SN, string WarningMsg, int FixtureNum)
        {
            CreatDirectory();

            try
            {
                if (!Warn_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    Warn_Log = Warn_LogPath + "\\" + Produce.Station.Name[FixtureNum].ToString() + "_Warn_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(Warn_Log))
                        File.AppendAllText(Warn_Log, "時間,SN,警告信息,治具\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + WarningMsg + "," + FixtureNum.ToString() + "\r\n";

                File.AppendAllText(Warn_Log, text);
            }
            catch (Exception ex)
            {

            }

        }

        public static void AddExceptionLog(string SN, string ExceptionMsg, int FixtureNum)
        {
            CreatDirectory();

            try
            {
                if (!Exception_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    Exception_Log = Exception_LogPath + "\\" + Produce.Station.Name[FixtureNum].ToString() + "_Exception_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(Exception_Log))
                        File.AppendAllText(Exception_Log, "時間,SN,異常信息,治具\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + SN + "," + ExceptionMsg + "," + FixtureNum.ToString() + "\r\n";

                File.AppendAllText(Exception_Log, text);
            }
            catch (Exception ex)
            {

            }
        }

        public static void AddRobotErrorLog(string SendCMD, string sErrorCode)
        {
            CreatDirectory();

            try
            {
                if (!RobotError_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    RobotError_Log = RobotError_LogPath + "\\RobotError_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(RobotError_Log))
                        File.AppendAllText(RobotError_Log, "時間,錯誤代碼,錯誤信息,發送指令\r\n");
                }
                string msg = ErrorCode.GetErrorInfo(sErrorCode);

                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text = nowTime + "," + sErrorCode + "," + msg.Replace(",", "-") + "," + SendCMD.Replace(",", "-") + "\r\n";

                File.AppendAllText(RobotError_Log, text);
            }
            catch (Exception ex)
            {

            }
        }


        public static void AddManualLog(string Type, string ManualObj, string oldstatus, string status)
        {
            CreatDirectory();

            try
            {
                if (!Manual_Log.Contains(DateTime.Now.ToString("yyyyMMdd")))
                {
                    Manual_Log = Manual_LogPath + "\\Manual_" + DateTime.Now.ToString("yyyyMMdd") + ".csv";
                    if (!File.Exists(Manual_Log))
                        File.AppendAllText(Manual_Log, "時間,職務,名稱,前後,類型,操作內容,狀態\r\n");
                }
                string nowTime = DateTime.Now.ToString("yyyyMMdd-HH:mm:ss");
                string text1 = nowTime + "," + Produce.UserJob + "," + Produce.LoginName + ",Old," + Type.Replace(",", "-") + "," + ManualObj.Replace(",", "-") + "," + oldstatus.Replace(",", "-") + "\r\n";
                string text2 = nowTime + "," + Produce.UserJob + "," + Produce.LoginName + ",New," + Type.Replace(",", "-") + "," + ManualObj.Replace(",", "-") + "," + status.Replace(",", "-") + "\r\n";
                File.AppendAllText(Manual_Log, text1);
                File.AppendAllText(Manual_Log, text2);
            }
            catch (Exception ex)
            {

            }
        }


    }
}
