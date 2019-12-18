using System;
using System.Collections.Generic;
//using System.Linq;
using System.Text;
//using ModbusSockettest;
using AutoMationTest.Robots;
using AutoMationTest.Common;
using System.Threading;
using System.Collections;
using System.Windows.Forms;


namespace AutoMationTest.Robots
{
    public class Robot
    {
        public enum RobotType
        {
            UR,
            Epson,
            TM,
            Denso,
            YAMAHA
        }

        public enum CommunicationType
        {
            Socket,
            ModbusSocket
        }

        public enum JiaZhua
        {
            JiaZhua1,
            JiaZhua2
        }

        public static bool IsConnected;
        public static string ReceiveMSG_From_Robot;
        public static string Errorcode;
        public static bool RobotDoneOver;

        public static ArrayList RobotDoingStation = new ArrayList();

        string lastreceive = "";

        private UR_Modbus _URModbus;
        private TM _URSocket;
        private Epson _epson;
        private TM _TM;
        private Denso _Denso;
        private YAMAHA _YAMAHA;

        private RobotType RobotName;
        private CommunicationType UsedCommType = CommunicationType.Socket;


        public Robot(RobotType _RobotType)
        {
            IsConnected = false;
            ReceiveMSG_From_Robot = "";
            Errorcode = "";
            RobotDoneOver = false;

            ErrorCode.LoadErrorCode();

            this.RobotName = _RobotType;

            switch (_RobotType)
            {

                case RobotType.UR:
                    UsedCommType = CommunicationType.Socket;
                    _URSocket = new TM();
                    //_URSocket.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data","Robot", "UR", "IP", "0");
                    _URSocket.port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "Port", "0"));

                    break;

                case RobotType.Epson:
                    bool buseuser2 = false;
                    _epson = new Epson();
                    _epson.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "IP", "");
                    _epson.SystemPort = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "SystemPort", "5000"));
                    _epson.UserPort = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort", "2000"));
                    try
                    {
                        _epson.UserPort2 = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort2", ""));
                        buseuser2 = true;
                    }
                    catch (Exception ex)
                    {
                        buseuser2 = false;
                    }
                    _epson.LoginPassword = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "LoginPassword", "");
                    _epson.RobotConnect(buseuser2);
                    break;

                case RobotType.TM:
                    _TM = new TM();
                    _TM.port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "TM", "Port", "0"));
                    break;

                case RobotType.Denso:
                    _Denso = new Denso();
                    _Denso.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "IP", "0");
                    _Denso.Port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "Port", "0"));
                    break;

                case RobotType.YAMAHA:
                    _YAMAHA = new YAMAHA();
                    _YAMAHA.Comport = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "COM", "COM1");
                    _YAMAHA.BaudRate = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "BaudRate", "0"));
                    break;
            }
        }

        public Robot(RobotType _RobotType, CommunicationType Ctype)
        {
            this.RobotName = _RobotType;

            switch (_RobotType)
            {

                case RobotType.UR:


                    switch (Ctype)
                    {
                        case CommunicationType.ModbusSocket:
                            UsedCommType = CommunicationType.ModbusSocket;
                            string IP = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "IP", "");
                            int Port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "Port", "502"));
                            _URModbus = new UR_Modbus(IP, Port);
                            break;
                        case CommunicationType.Socket:
                            UsedCommType = CommunicationType.Socket;
                            _URSocket = new TM();
                            //_URSocket.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data","Robot", "UR", "IP", "0");
                            _URSocket.port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "UR", "Port", "0"));
                            break;
                    }
                    break;

                case RobotType.Epson:
                    bool buseuser2 = false;
                    _epson = new Epson();
                    _epson.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "IP", "");
                    _epson.SystemPort = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "SystemPort", "5000"));
                    _epson.UserPort = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort", "2000"));
                    try
                    {
                        _epson.UserPort2 = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "UserPort2", ""));
                        buseuser2 = true;
                    }
                    catch (Exception ex)
                    {
                        buseuser2 = false;
                    }
                    _epson.LoginPassword = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Epson", "LoginPassword", "");
                    _epson.RobotConnect(buseuser2);
                    break;

                case RobotType.TM:
                    _TM = new TM();
                    _TM.port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "TM", "Port", "0"));
                    break;

                case RobotType.Denso:
                    _Denso = new Denso();
                    _Denso.IP = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "IP", "0");
                    _Denso.Port = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "Denso", "Port", "0"));
                    break;
                case RobotType.YAMAHA:
                    _YAMAHA = new YAMAHA();
                    _YAMAHA.Comport = Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "COM", "COM1");
                    _YAMAHA.BaudRate = Convert.ToInt32(Common.INI.ReadINI(Application.StartupPath + "\\Data", "Robot", "YAMAHA", "BaudRate", "0"));


                    break;
            }
        }

        public void Connect()
        {
            Log.AddMainLog("Connect to Robot： " + RobotName);
            switch (this.RobotName)
            {
                case RobotType.UR:
                    //modubus通訊無需調用此方法，在發送指令時會自動連接
                    if (UsedCommType == CommunicationType.Socket)
                    {
                        _URSocket.RobotConnect();
                    }

                    break;
                case RobotType.Epson:
                    _epson.ResetRobot();
                    break;

                case RobotType.TM:
                    _TM.RobotConnect();
                    break;

                case RobotType.Denso:
                    _Denso.ConnectRobot();
                    break;

                case RobotType.YAMAHA:
                    _YAMAHA.ConnectRobot();
                    break;

                default:
                    break;
            }
        }

        public void DisConnect()
        {
            Log.AddMainLog("Disconnect Robot： " + RobotName);
            switch (this.RobotName)
            {
                case RobotType.UR:
                    if (UsedCommType == CommunicationType.Socket)
                    {
                        _URSocket.DisconnetRobot();
                    }
                    break;
                case RobotType.Epson:
                    _epson.DisConnectRobot();
                    break;

                case RobotType.TM:
                    _TM.DisconnetRobot();
                    break;

                case RobotType.Denso:
                    _Denso.DisconnectRobot();
                    break;

                case RobotType.YAMAHA:
                    _YAMAHA.DisconnectRobot();
                    break;

                default:
                    break;
            }
        }

        public void SendToRobot(string cmd, bool ClearLastReceive)
        {
            RobotDoneOver = false;
            //Log.AddMainLog("[" + RobotName + "] Send:" + cmd);
            switch (this.RobotName)
            {
                case RobotType.UR:
                    if (UsedCommType == CommunicationType.Socket)
                    {
                        _URSocket.SendToRobot(cmd, ClearLastReceive);
                    }
                    break;
                case RobotType.Epson:
                    _epson.SendMsg(cmd, ClearLastReceive);
                    break;

                case RobotType.TM:
                    _TM.SendToRobot(cmd, ClearLastReceive);
                    break;

                case RobotType.Denso:
                    _Denso.SendMsg(cmd, ClearLastReceive);
                    break;

                case RobotType.YAMAHA:
                    _YAMAHA.SendToRobot(cmd, ClearLastReceive);
                    break;

                default:
                    break;
            }
        }

        public void SendToRobot(int Address, string Value)
        {
            RobotDoneOver = false;
            switch (this.RobotName)
            {
                case RobotType.UR:
                    if (UsedCommType == CommunicationType.ModbusSocket)
                    {
                        _URModbus.Send(Address, Value);
                    }
                    break;

                default:
                    break;
            }
        }

        public bool SendCheckRobot(string cmd, string CheckOKStr, int timeout, bool ClearLastReceive, ref string ErrorMsg)
        {
            Errorcode = "";
            ErrorMsg = "";

            if (IsConnected)
            {
                Log.AddMainLog("[" + RobotName + "] Send:" + cmd);
                SendToRobot(cmd, ClearLastReceive);
                Log.AddMainLog("Check msg:\"" + CheckOKStr + "\"");

                DateTime dt = DateTime.Now;
                while (true)
                {
                    if (ReceiveMSG_From_Robot != lastreceive)
                    {
                        lastreceive = ReceiveMSG_From_Robot;
                        Log.AddMainLog("[" + RobotName + "] Receive:" + ReceiveMSG_From_Robot);
                    }

                    if (ReceiveMSG_From_Robot.Contains(CheckOKStr))
                    {
                        RobotDoneOver = true;
                        Log.AddMainLog("[" + RobotName + "] 當前動作已完成!");
                        return true;
                    }

                    if (ReceiveMSG_From_Robot.Contains("_ERROR"))
                    {
                        string msg = ReceiveMSG_From_Robot.Replace("\r", "").Replace("\n", "").Trim();
                        Errorcode = msg.Substring(0, msg.IndexOf("_ERROR"));
                        ErrorMsg = ErrorCode.GetErrorInfo(Errorcode);
                        Log.AddMainLog("[ErrorCode]:" + Errorcode + ",Robot Error:" + ErrorMsg);
                        Log.AddRobotErrorLog(cmd, Errorcode);
                        Produce.bNeedBaoJing = true;
                        Produce.RobotWarning = "異常:" + ErrorMsg;
                        break;
                    }

                    if (timeout != 0)
                    {
                        if (dt.AddSeconds(timeout) < DateTime.Now)
                        {
                            Log.AddMainLog(timeout.ToString() + "s Timeout,Robot Fail!");
                            Log.AddRobotErrorLog(cmd, "TIME01");
                            Produce.bNeedBaoJing = true;
                            Produce.RobotWarning = "手臂:" + ErrorMsg;
                            break;
                        }
                    }

                    Thread.Sleep(50);

                }
            }

            return false;
        }

        public bool SendCheckRobot_Station(ArrayList testList, int timeout, bool ClearLastReceive, ref string ErrorMsg)
        {
            if (true)//(IsConnected)
            {
                Errorcode = "";
                ErrorMsg = "";

                RobotDoingStation.Clear();

                for (int p1 = 0; p1 < testList.Count; p1++)
                {
                    Produce.RobotDoneOver_ByStation[p1] = false;
                    RobotDoingStation.Add(Convert.ToInt32(testList[p1]));

                }

                for (int p2 = 0; p2 < testList.Count; p2++)
                {
                    MessageBox.Show(testList[p2].ToString() + "取放");
                    Produce.RobotDoneOver_ByStation[p2] = true;
                    MessageBox.Show(testList[p2].ToString() + "取放完成");
                }

                return true;

                //DateTime dt = DateTime.Now;
                //while (true)
                //{
                //    if (ReceiveMSG_From_Robot != lastreceive)
                //    {
                //        lastreceive = ReceiveMSG_From_Robot;
                //        Log.AddMainLog("[" + RobotName + "] Receive:" + ReceiveMSG_From_Robot);
                //    }



                //    if (timeout != 0)
                //    {
                //        if (dt.AddSeconds(timeout) < DateTime.Now)
                //        {
                //            Log.AddMainLog(timeout.ToString() + "s Timeout,Robot Fail!");
                //            break;
                //        }
                //    }

                //    Thread.Sleep(50);

                //}
            }

            return false;
        }




        public void SendSystemMsg_Only_Epson(string systemcmd)
        {
            if (RobotName == RobotType.Epson)
            {
                _epson.send(systemcmd);
            }
        }

        public void SendReadEpson202(string cmd, string checkmsg, ref string sreceve)
        {
            if (RobotName == RobotType.Epson)
            {
                _epson.SendCheck202(cmd, checkmsg, ref  sreceve);

            }
        }

        public void SendEpson202(string cmd)
        {
            if (RobotName == RobotType.Epson)
            {
                _epson.Send202(cmd);

            }
        }

        public void Dispose()
        {
            switch (this.RobotName)
            {
                case RobotType.UR:
                    if (UsedCommType == CommunicationType.Socket)
                    {
                        _URSocket.DisconnetRobot();
                        _URSocket = null;
                    }
                    break;
                case RobotType.Epson:
                    _epson.DisConnectRobot();
                    _epson.Close();
                    _epson = null;
                    break;

                case RobotType.TM:
                    _TM.DisconnetRobot();
                    _TM = null;
                    break;

                case RobotType.Denso:
                    _Denso.DisconnectRobot();
                    _Denso = null;
                    break;

                case RobotType.YAMAHA:
                    _YAMAHA.DisconnectRobot();
                    _YAMAHA = null;
                    break;
            }
        }
    }
}
