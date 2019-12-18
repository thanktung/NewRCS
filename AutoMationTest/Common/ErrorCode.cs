using System;
using System.Collections.Generic;
using System.Text;
using System.IO;
using System.Windows.Forms;

namespace AutoMationTest.Common
{
    public class ErrorCode
    {
        public static void LoadErrorCode()
        {
            ErrorMsgs = File.ReadAllLines(Application.StartupPath + "\\ErrorCode\\ErrorCode.csv",Encoding.GetEncoding("big5"));
        }
        public static string[] ErrorMsgs;

        public static string GetErrorInfo(string ErrorCode)
        {
            string msg = "未知";
            for (int i = 0; i < ErrorMsgs.Length; i++)
            {
                string[] ssplit = ErrorMsgs[i].Split(',');
                if (ErrorCode.Contains(ssplit[0]) && ssplit[0].Trim() != "")
                {
                    try
                    {
                        msg = ssplit[1];
                    }
                    catch (Exception ex) { }

                    break;
                }
            }
            return msg;
        }


    }
}
