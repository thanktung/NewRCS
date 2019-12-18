using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;
using AutoMationTest.ATS;
using System.Net.Sockets;
using System.Net;
using AutoMationTest.Function;

namespace AutoMationTest.UI
{
    public partial class TestUI : UserControl
    {
        public TestUI()//(int nStationNumber, string IP, int Port)
        {
            this.SetStyle(ControlStyles.UserPaint, true);
            this.SetStyle(ControlStyles.ResizeRedraw, true);
            this.SetStyle(ControlStyles.AllPaintingInWmPaint, true);
            this.SetStyle(ControlStyles.OptimizedDoubleBuffer, true);

            InitializeComponent();
            if (!Produce.bAlreadyGetStationInfo)
            {
                Produce.GetStationInfo();
            }

        }

        public struct Action
        {
            public string StationNumber;
            public Produce.RobotCMD robotCmd;
            public Status UserControlStatus;
            public string ResponeServerMsg;
        }

        private const string CategoryName = "ATS模塊";

        #region UI Setting
        private int StationIndex;
        private int nStationNum;
        private string sStationNum;
        private string sStationName;
        Thread showthread;
        public int nTimeOut = 0;
        //public ATS_Client ATSClient;
        public bool bGoldenSample = false;
        public bool bPutGolden = false;
        public bool bGoldenTestOver = false;

        FrmChangeStatus frm_Status;
        private bool bmanualstatus = false;
        public int BeginTime = 0;
        public bool bShowTime = false;
        public double rate;
        public double total;
        public bool bWarning = true;//是否報警
        public bool bAlreadyTestGolden = false;
        public bool bTXPowerTest = false;
        public bool bAlreadyTestTXPower = false;
        #endregion

        #region ATS Client
        public int DUTTestTime = 0;
        private Socket ClientSocket;
        private bool bmanualstop = false;
        private string sIP = "127.0.0.1";
        private int sPort = 5004;
        private Thread ReceiveServerThread; //持續接收Server msg線程
        private Thread SendServerThread;//持續發送Server msg線程
        private Thread HeartBeatThread;//持續發送Server心跳包線程
        private string WarningShowMsg = "";

        CycleQueue ServerQ;//接收ATS消息隊列
        CycleQueue ServerBuffQ;//ATS消息Buffer隊列
        string Barcode = "";
        public bool bGoldenSampleBarcode = true;
        IPEndPoint RemoteEP;
        string receive = "";
        object msg;
        int NGWarningTimes;
        public FixStatus fix_status = FixStatus.None;
        public Action action;

        public enum FixStatus
        {
            None,
            Error,
            Open,
            Close
        }

        #endregion

        #region 屬性
        private double _passCount = 0;
        [Category(CategoryName)]
        [Description("ATSPass數量")]
        [DefaultValue(0)]
        public double PassCount
        {
            get
            {
                return _passCount;
            }
            set
            {

                _passCount = value;
                total = _passCount + NGCount + WarningCount;

                if (NGCount == 0)
                {
                    rate = 100;
                }
                else
                {
                    rate = Math.Round(PassCount / (PassCount + NGCount) * 100, 2);
                }
                //INI.WriteINI(Application.StartupPath + "\\Data","Test", "Fix_" + sStationNum, "Pass", _passCount.ToString());
                //INI.WriteINI(Application.StartupPath + "\\Data","Test", "Fix_" + sStationNum, "Total", total.ToString());
                SetTextBoxCallback(textBox_TOTAL, total.ToString());
                SetTextBoxCallback(textBox_YR, rate.ToString() + "%");
            }
        }

        private double _ngCount = 0;
        [Category(CategoryName)]
        [Description("ATSNG數量")]
        [DefaultValue(0)]
        public double NGCount
        {
            get
            {
                return _ngCount;
            }
            set
            {

                _ngCount = value;
                total = PassCount + _ngCount + WarningCount;
                if (NGCount == 0)
                {
                    rate = 100;
                }
                else
                {
                    rate = Math.Round(PassCount / (PassCount + NGCount) * 100, 2);
                }

                SetTextBoxCallback(textBox_NG, _ngCount.ToString());
                SetTextBoxCallback(textBox_TOTAL, total.ToString());
                SetTextBoxCallback(textBox_YR, rate.ToString() + "%");

            }
        }

        private double _warningCount = 0;
        [Category(CategoryName)]
        [Description("ATS報警數量")]
        [DefaultValue(0)]
        public double WarningCount
        {
            get
            {
                return _warningCount;
            }
            set
            {

                _warningCount = value;
                total = PassCount + NGCount + _warningCount;

                SetTextBoxCallback(textBox_TOTAL, total.ToString());
            }
        }

        private string _sn = "NONE";
        [Category(CategoryName)]
        [Description("SN號碼")]
        [DefaultValue("NONE")]
        public string SN
        {
            get
            {
                return _sn;
            }
            set
            {

                _sn = value;

                SetProgressBarText(progressBar1, _sn);

            }
        }



        private string _ngitem = "NG:NULL";
        [Category(CategoryName)]
        [Description("NG測項名稱")]
        [DefaultValue("NULL")]
        public string NGItem
        {
            get
            {
                return _ngitem;
            }
            set
            {
                _ngitem = value;
                SetProgressBarText(progressBar1, _ngitem);
            }
        }

        private string _ngvalue = "NULL";
        [Category(CategoryName)]
        [Description("NG測項的值")]
        [DefaultValue("NULL")]
        public string NGValue
        {
            get
            {
                return _ngvalue;
            }
            set
            {
                _ngvalue = value;
            }
        }

        private string _warnmsg = "Warning:NULL";
        [Category(CategoryName)]
        [Description("ATS警告信息")]
        [DefaultValue("Warning:NULL")]
        public string WarningMSG
        {
            get
            {
                return _warnmsg;
            }
            set
            {
                _warnmsg = value;
                SetProgressBarText(progressBar1, _warnmsg);
            }
        }

        private int _stationnumber = 1;
        [Category(CategoryName)]
        [Description("治具編號數")]
        [DefaultValue(1)]
        public int StationNumber
        {
            get
            {
                return _stationnumber;
            }
            set
            {
                _stationnumber = value;
                nStationNum = StationNumber;
                sStationNum = StationNumber.ToString();
                sStationName = Produce.Station.Name[StationNumber].ToString();
                TimeOut = Convert.ToInt32(Produce.Station.TimeOut[sStationName]);

                this.IP = INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[0];
                this.Port = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[1]);


                UINumber.Text = sStationNum;
                StationName.Text = sStationName;
                progressBar1.PositionMax = TimeOut;
                progressBar1.Text = progressBar1.PositionMax.ToString() + " S";
            }
        }

        [Category(CategoryName)]
        [Description("ATS所在PC的IP地址")]
        [DefaultValue("127.0.0.1")]
        public string IP
        {
            get
            {
                sIP = INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[0];
                return sIP;
            }
            set
            {
                sIP = value;
                RemoteEP = new IPEndPoint(IPAddress.Parse(IP), Port);
                //INI.WriteINI(Application.StartupPath + "\\Data","Setting", "ATS_IP_Port", "ATS" + sStationNum, sIP + "," + Port.ToString());
            }
        }

        [Category(CategoryName)]
        [Description("超時報警時間")]
        [DefaultValue("500")]
        public int TimeOut
        {
            get
            {
                return nTimeOut;
            }
            set
            {
                nTimeOut = value;
                progressBar1.PositionMax = nTimeOut;
                progressBar1.Text = progressBar1.PositionMax.ToString() + " S";
            }
        }

        [Category(CategoryName)]
        [Description("ATS所在PC的網絡端口")]
        [DefaultValue(5004)]
        public int Port
        {
            get
            {
                sPort = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[1]);
                return sPort;
            }
            set
            {
                sPort = value;
                RemoteEP = new IPEndPoint(IPAddress.Parse(IP), sPort);
                //INI.WriteINI(Application.StartupPath + "\\Data","Setting", "ATS_IP_Port", "ATS" + sStationNum, IP + "," + sPort.ToString());
            }
        }

        public enum Status
        {
            NotUsed,
            Used,
            NoDUT,
            Testing,
            Pass,
            NG,
            Warning,
            WaitDUT,
            DUTIN,
            Manual,
            Stop,
            Start,
            PassDUT,
            NGDUT,
            NewDUT,
            Retest
        }

        private Status _status = Status.NotUsed;
        public Status status
        {
            get
            {
                return _status;
            }
            set
            {

                _status = value;

                switch (_status)
                {
                    case Status.NoDUT:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "No DUT", Color.FromArgb(200, 200, 200));
                        SetLabelTextCallback(bt_Status, "No DUT", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        break;
                    case Status.Testing:

                        SetProgressBar(progressBar1, 0);
                        bShowTime = true;
                        BeginTime = 1;
                        this.SN = "NONE";
                        this.NGItem = "NG:NULL";
                        this.NGValue = "NULL";
                        this.WarningMSG = "Warning:NULL";
                        SetProgressBarText(progressBar1, SN);
                        //SetLabelTextCallback(label_Status, "0", Color.Blue);
                        SetLabelTextCallback(bt_Status, "0", Color.Blue);
                        Produce.yulans.SetStation(StationNumber, Color.Blue);
                        break;
                    case Status.Pass:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "Pass", Color.FromArgb(0, 200, 50));
                        SetLabelTextCallback(bt_Status, "Pass", Color.FromArgb(0, 200, 50));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(0, 200, 50));
                        SetProgressBar(progressBar1, TimeOut);
                        if (!bmanualstatus)
                        {
                            Log.AddAllDUTLog(this.SN, Log.TestResult.Pass, Convert.ToInt32(UINumber.Text));
                        }
                        break;
                    case Status.NG:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "NG", Color.FromArgb(220, 0, 0));
                        SetLabelTextCallback(bt_Status, "NG", Color.FromArgb(220, 0, 0));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(220, 0, 0));
                        SetProgressBar(progressBar1, TimeOut);
                        if (!bmanualstatus)
                        {
                            Log.AddAllDUTLog(this.SN, Log.TestResult.NG, Convert.ToInt32(UINumber.Text));
                            Log.AddNGLog(this.SN, this.NGItem, NGValue, Convert.ToInt32(UINumber.Text));
                        }
                        break;

                    case Status.Retest:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "NG", Color.FromArgb(220, 0, 0));
                        SetLabelTextCallback(bt_Status, "Retest", Color.DarkSalmon);
                        Produce.yulans.SetStation(StationNumber, Color.DarkSalmon);
                        SetProgressBar(progressBar1, TimeOut);
                        if (!bmanualstatus)
                        {
                            Log.AddAllDUTLog(this.SN, Log.TestResult.Retest, Convert.ToInt32(UINumber.Text));
                            Log.AddWarningLog(this.SN, this.WarningMSG + "-待複測", Convert.ToInt32(UINumber.Text));
                        }
                        break;

                    case Status.Warning:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "Warning", Color.FromArgb(250, 230, 50));
                        SetLabelTextCallback(bt_Status, "Warning", Color.FromArgb(250, 230, 50));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(250, 230, 50));
                        //SetJianBianButtonColor(bt_Status, "Warning", Color.Yellow, Color.FromArgb(64, 64, 0));

                        SetProgressBar(progressBar1, TimeOut);
                        if (!bmanualstatus)
                        {
                            Log.AddAllDUTLog(this.SN, Log.TestResult.Warning, Convert.ToInt32(UINumber.Text));
                            Log.AddWarningLog(this.SN, this.WarningMSG, Convert.ToInt32(UINumber.Text));
                        }
                        break;
                    case Status.WaitDUT:

                        bShowTime = false;
                        BeginTime = 0;
                        this.SN = "NONE";
                        this.NGItem = "NG:NULL";
                        this.NGValue = "NULL";
                        this.WarningMSG = "Warning:NULL";
                        //SetLabelTextCallback(label_Status, "Wait DUT", Color.FromArgb(0x80, 0, 0x80));
                        SetLabelTextCallback(bt_Status, "Wait DUT", Color.FromArgb(0x80, 0, 0x80));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(0x80, 0, 0x80));
                        //SetJianBianButtonColor(bt_Status, "Wait DUT", Color.Fuchsia, Color.FromArgb(64, 0, 64));

                        SetProgressBar(progressBar1, 0);
                        SetProgressBarText(progressBar1, SN);
                        break;

                    case Status.DUTIN:

                        bShowTime = false;
                        BeginTime = 0;
                        this.SN = "NONE";
                        this.NGItem = "NG:NULL";
                        this.NGValue = "NULL";
                        this.WarningMSG = "Warning:NULL";
                        //SetLabelTextCallback(label_Status, "Wait DUT", Color.FromArgb(0x80, 0, 0x80));
                        SetLabelTextCallback(bt_Status, "DUT IN", Color.FromArgb(0x80, 0, 0x80));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(0x80, 0, 0x80));
                        //SetJianBianButtonColor(bt_Status, "Wait DUT", Color.Fuchsia, Color.FromArgb(64, 0, 64));

                        SetProgressBar(progressBar1, 0);
                        SetProgressBarText(progressBar1, SN);
                        break;
                    case Status.Manual:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "手動", Color.DimGray);
                        SetLabelTextCallback(bt_Status, "手動", Color.DimGray);
                        Produce.yulans.SetStation(StationNumber, Color.DimGray);
                        SetProgressBar(progressBar1, 0);
                        break;
                    case Status.Stop:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "中止", Color.FromArgb(200, 200, 200));
                        SetLabelTextCallback(bt_Status, "中止", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        break;
                    case Status.Start:
                        bShowTime = false;
                        BeginTime = 0;
                        //SetLabelTextCallback(label_Status, "開始", Color.FromArgb(200, 200, 200));
                        SetLabelTextCallback(bt_Status, "開始", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        break;
                    case Status.PassDUT:
                        bShowTime = false;
                        BeginTime = 0;
                        SetLabelTextCallback(bt_Status, "Pass", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        //SetJianBianButtonColor(bt_Status, "Pass", Color.Lime, Color.FromArgb(0, 64, 0));
                        break;
                    case Status.NGDUT:
                        bShowTime = false;
                        BeginTime = 0;
                        SetLabelTextCallback(bt_Status, "NG", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        //SetJianBianButtonColor(bt_Status, "NG", Color.Red, Color.FromArgb(64, 0, 0));
                        break;
                    case Status.NewDUT:
                        bShowTime = false;
                        BeginTime = 0;
                        SetLabelTextCallback(bt_Status, "New", Color.FromArgb(200, 200, 200));
                        Produce.yulans.SetStation(StationNumber, Color.FromArgb(200, 200, 200));
                        break;
                    case Status.NotUsed:

                        Produce.yulans.SetStation(StationNumber, Color.Gray);
                        break;

                    case Status.Used:
                        bShowTime = false;
                        BeginTime = 0;
                        SetLabelTextCallback(bt_Status, "Used", Color.LightSkyBlue);
                        Produce.yulans.SetStation(StationNumber, Color.Gray);
                        break;
                }


            }
        }
        #endregion


        public void Timer()
        {
            int i = 0;
            bool alreadyWarning = false;
            while (true)
            {
                if (BeginTime == 1)  //BeginTime=1表示開始計時，BeginTime=0表示不計時
                {
                    i++;
                    if (bShowTime)
                    {

                        //SetLabelTextCallback(label_Status, i.ToString(), Color.Blue);
                        SetLabelTextCallback(bt_Status, i.ToString(), Color.Blue);
                        if (i <= TimeOut)
                        {
                            SetProgressBar(progressBar1, i);
                        }
                        else
                        {
                            if (i % 2 == 0)
                            {
                                SetProgressBarText(progressBar1, "" + TimeOut.ToString() + "S 已超時");
                            }
                            else
                            {
                                SetProgressBarText(progressBar1, this.SN);
                            }
                        }
                        if (this.bWarning && !alreadyWarning && (i >= TimeOut))
                        {

                            Produce.bNeedBaoJing = true;
                            Produce.MainWarning = Produce.Station.Name[StationNumber].ToString() + "站 [" + sStationNum + "] 號治具" + "超時";

                            Log.AddExceptionLog(SN, "超時報警", StationNumber);

                            alreadyWarning = true;

                        }
                    }
                }
                else
                {
                    i = 0;
                    alreadyWarning = false;
                }
                Thread.Sleep(1000);
            }
        }

        private void ShowProgress()
        {
            int max = Convert.ToInt32(Produce.Station.TimeOut[StationName.Text]);
            for (int i = 0; i < max; i++)
            {
                SetProgressBar(progressBar1, i + 1);
            }
            Thread.Sleep(50);
            SetProgressBar(progressBar1, 0);
        }

        private void checkBox1_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox_Used.Checked)
            {
                panel_used.Visible = false;
                //this.BackColor = Color.LightSkyBlue;
                UINumber.BackColor = Color.White;
                this.progressBar1.ColorText = Color.Black;
                this.progressBar1.Position = 0;
                progressBar1.Enabled = true;
                progressBar1.Text = progressBar1.PositionMax.ToString() + " S";
                //if (showthread != null)
                //{
                //    if (showthread.IsAlive)
                //    {
                //        showthread.Abort();
                //    }
                //}
                //showthread = new Thread(new ThreadStart(ShowProgress));
                //showthread.Start();

                this.radioButton1.Checked = true;

                //textBox_TOTAL.Text = "0";
                //textBox_NG.Text = "0";
                textBox_LianxuNG.Text = NGWarningTimes.ToString();
                //textBox_YR.Text = "0.00%";

                //label_Status.BackColor = Color.LightSkyBlue;
                //label_Status.ForeColor = Color.Black;
                //label_Status.Text = "Used";
                bt_Status.Enabled = true;
                //bt_Status.BackColor = Color.LightSkyBlue;
                ////Produce.yulans.SetStation(StationNumber, Color.LightSkyBlue);
                ////bt_Status.CenterColor = Color.LightCyan;
                ////bt_Status.SurroundColor = Color.LightSkyBlue;
                //bt_Status.Text = "Used";

                button1.BackColor = Color.RosyBrown;
                panel1.BackColor = Color.LightCyan;
                //panel1.CenterColor = Color.LightCyan;
                //panel1.SurroundColor = Color.WhiteSmoke;
                //panel3.BackColor = Color.Black;
                panel3.Enabled = true;

                panel2.BackColor = Color.BlanchedAlmond;
                panel2.Enabled = true;

                this.status = Status.Used;
            }
            else
            {

                BeginTime = 0;
                panel_used.Visible = true;
                UINumber.BackColor = Color.WhiteSmoke;
                this.progressBar1.ColorText = Color.Gray;
                this.progressBar1.Text = progressBar1.PositionMax.ToString() + " S";
                progressBar1.Enabled = false;
                this.progressBar1.Position = 0;

                //textBox_TOTAL.Text = "總數";
                //textBox_NG.Text = "不良";
                //textBox_LianxuNG.Text = "連續不良";
                //textBox_YR.Text = "良率";

                //label_Status.BackColor = Color.LightGray;
                //label_Status.ForeColor = Color.White;
                //label_Status.Text = "No Used";
                bt_Status.Enabled = false;
                bt_Status.BackColor = Color.LightGray;
                //Produce.yulans.SetStation(StationNumber, Color.Gray);
                bt_Status.Text = "No Used";

                button1.BackColor = Color.DarkGray;

                panel1.BackColor = Color.Silver;
                //panel1.CenterColor = Color.Silver;
                //panel1.SurroundColor = Color.WhiteSmoke;

                panel3.BackColor = Color.Silver;
                panel3.Enabled = false;

                panel2.BackColor = Color.Silver;
                panel2.Enabled = false;

                this.status = Status.NotUsed;
            }
        }

        private void radioButton1_CheckedChanged(object sender, EventArgs e)
        {
            if (radioButton1.Checked)
            {
                bGoldenSample = false;
                Produce.bTestGolden[StationNumber - 1] = false;
                Log.AddMainLog("[" + sStationName + "_" + sStationNum + "] 開啟 [正常品] 測試");
            }
            else
            {
                bGoldenSample = true;
                bAlreadyTestGolden = false;
                Produce.bTestGolden[StationNumber - 1] = true;
                Log.AddMainLog("[" + sStationName + "_" + sStationNum + "] 開啟 [標準件] 測試");
            }
        }

        private void TestUI_Load(object sender, EventArgs e)
        {

            nStationNum = StationNumber;
            sStationNum = StationNumber.ToString();
            sStationName = Produce.Station.Name[StationNumber].ToString();
            StationIndex = Convert.ToInt16(Produce.Station.Index[StationNumber]);
            TimeOut = Convert.ToInt32(Produce.Station.TimeOut[sStationName]);
            UINumber.Text = sStationNum;
            StationName.Text = sStationName;
            //progressBar1.PositionMax = TimeOut;
            //progressBar1.Text = progressBar1.PositionMax.ToString() + " S";

            PassCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Pass", "0"));
            NGCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "NG", "0"));
            WarningCount = Convert.ToDouble(INI.ReadINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Warning", "0"));

            this.IP = INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[0];
            this.Port = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "Setting", "ATS_IP_Port", "ATS" + sStationNum, "127.0.0.1,5004").Split(',')[1]);


            ServerQ = new CycleQueue(50);
            ServerBuffQ = new CycleQueue(1000);
            ClientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            RemoteEP = new IPEndPoint(IPAddress.Parse(IP), Port);

            Thread TimerThread = new Thread(new ThreadStart(Timer));
            TimerThread.Start();

            Thread connectthread = new Thread(new ThreadStart(ATSConnect));
            connectthread.Start();

            Thread goldenCheckthread = new Thread(new ThreadStart(CheckGolden));
            goldenCheckthread.Start();
        }

        private void CheckGolden()
        {
            while (true)
            {

                Thread.Sleep(1000);

                try
                {
                    if (Produce.bTestGolden[StationNumber - 1])
                    {
                        if (!bGoldenSample)
                        {
                            SetRadioButton(radioButton2, true);
                        }
                    }
                    else
                    {
                        if (bGoldenSample)
                        {
                            SetRadioButton(radioButton1, true);
                        }
                    }

                    if (checkBox_Used.Checked && !bGoldenSample)
                    {

                        if (Produce.Station.GoldenTestTime.Contains(StationNumber))
                        {
                            string settime = Produce.Station.GoldenTestTime[StationNumber].ToString();
                            if (settime.Contains(":"))
                            {
                                string sHour = settime.Split(':')[0];
                                string sMinute = settime.Split(':')[1];

                                DateTime dt = DateTime.Now;
                                if (dt.Hour.ToString() == sHour && dt.Minute.ToString() == sMinute)
                                {
                                    Log.AddMainLog("[每天] [" + sStationName + "_" + sStationNum + "] 預定的標準件測試時間 [" + settime + "] 達到");
                                    SetRadioButton(radioButton2, true);
                                }
                            }
                        }

                        if (Produce.Station.GoldenTestTimeOnce.Contains(StationNumber))
                        {
                            string settime = Produce.Station.GoldenTestTimeOnce[StationNumber].ToString();
                            if (settime.Contains(":"))
                            {
                                string sHour = settime.Split(':')[0];
                                string sMinute = settime.Split(':')[1];

                                DateTime dt = DateTime.Now;
                                if (dt.Hour.ToString() == sHour && dt.Minute.ToString() == sMinute)
                                {
                                    Log.AddMainLog("[一次] [" + sStationName + "_" + sStationNum + "] 預定的標準件測試時間 [" + settime + "] 達到");
                                    SetRadioButton(radioButton2, true);
                                    Produce.ClearGoldenSetting(StationNumber);
                                }
                            }
                        }
                    }
                }
                catch (Exception ex)
                { }
            }


        }

        private void button1_Click(object sender, EventArgs e)
        {
            if (Produce.bLoginOK)
            {
                if (this.status != Status.Testing)
                {
                    Thread _ChangeStatus = new Thread(new ThreadStart(ChangeStatus));
                    _ChangeStatus.Start();
                }
                else
                {
                    ShowWarmForm("[" + sStationNum + "] 測試中，禁止手動操作！");
                }
            }
            else
            {
                ShowWarmForm("未登錄，無法手動操作！");
            }
        }


        private void ShowWarmForm(string WarnMsg)
        {
            Log.AddMainLog("警告:" + WarnMsg);
            WarningShowMsg = WarnMsg;
            Thread thwarn = new Thread(new ThreadStart(ThreadWarmForm));
            thwarn.Start();
        }

        private void ThreadWarmForm()
        {
            WarningForm wf = new WarningForm(WarningShowMsg);
            wf.Show();
            wf.Refresh();
            Thread.Sleep(1000);
            wf.Close();
        }

        public void ChangeStatus()
        {

            if (!Produce.bManualChangeStatus)
            {
                Produce.bManualChangeStatus = true;
                frm_Status = new FrmChangeStatus(UINumber.Text);
                frm_Status.StartPosition = FormStartPosition.Manual;
                frm_Status.Location = new Point(MousePosition.X + 30, MousePosition.Y - 220);
                //Action action;
                if (checkBox_Used.Checked)
                {
                    frm_Status.comboBox1.Text = "5";
                }

                frm_Status.sStatus = "0";
                frm_Status.ShowDialog();

                if (!checkBox_Used.Checked)
                {
                    return;
                }

                if (Produce.bLoginOK && this.status != Status.Testing && IsConnected())
                {
                    if (frm_Status.sStatus != "0")
                    {
                        int ChoiceStatus = Convert.ToInt16(frm_Status.sStatus);

                        if (Produce.QUEUE.Check(sStationNum))
                        {
                            bmanualstatus = true;

                            if (ChoiceStatus == 1)//取板到Pass區域(無信號)
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，取板到Pass區域(無信號)");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "取板到Pass區域(無信號)");

                                status = Status.Manual;

                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.PASS;
                                action.UserControlStatus = Status.NoDUT;
                                action.ResponeServerMsg = "MANUAL_CLEAR_NOSINGLE";

                                Produce.QUEUE.In_Check(action);

                            }
                            else if (ChoiceStatus == 2)//取板到NG區域(無信號)
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，取板到NG區域(無信號)");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "取板到NG區域(無信號)");
                                status = Status.Manual;

                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.NG;
                                action.UserControlStatus = Status.NoDUT;
                                action.ResponeServerMsg = "MANUAL_CLEAR_NOSINGLE";

                                Produce.QUEUE.In_Check(action);
                            }
                            else if (ChoiceStatus == 3)//放板到治具(無信號)
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，放板到治具(無信號)");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "放板到治具(無信號)");
                                status = Status.Manual;
                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.Put;
                                action.UserControlStatus = Status.DUTIN;
                                action.ResponeServerMsg = "MANUAL_PUT_NOSINGLE";

                                Produce.QUEUE.In_Check(action);

                            }
                            else if (ChoiceStatus == 4)//放板到治具
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，請求放板");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "請求放板");
                                status = Status.WaitDUT;

                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.Put;
                                action.UserControlStatus = Status.Testing;
                                action.ResponeServerMsg = "CtoT_placeDUTOK";
                                Produce.QUEUE.In_Check(action);

                            }
                            else if (ChoiceStatus == 5)//測試結束, 回饋Pass結果,換板
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，交換Pass板");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "交換Pass板");
                                status = Status.Pass;

                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.PASS;
                                action.UserControlStatus = Status.Testing;
                                action.ResponeServerMsg = "CtoT_placeDUTOK";
                                Produce.QUEUE.In_Check(action);

                            }
                            else if (ChoiceStatus == 6)//測試結束, 回饋NG結果,換板
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，交換NG板");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "交換NG板");
                                status = Status.NG;

                                action.StationNumber = UINumber.Text;
                                action.robotCmd = Produce.RobotCMD.NG;
                                action.UserControlStatus = Status.Testing;
                                action.ResponeServerMsg = "CtoT_placeDUTOK";
                                Produce.QUEUE.In_Check(action);

                            }
                            else if (ChoiceStatus == 7)//測試結束, 回饋Retest結果,換板
                            {
                                int retestBuffCount = Convert.ToInt32(Produce.Station.ReTestBuffer[StationName.Text]);
                                if (retestBuffCount > 0)
                                {

                                    Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，複測信號");
                                    Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "複測信號");
                                    status = Status.Retest;

                                    action.StationNumber = UINumber.Text;
                                    action.robotCmd = Produce.RobotCMD.Retest;
                                    action.UserControlStatus = Status.Testing;
                                    action.ResponeServerMsg = "CtoT_placeDUTOK";
                                    Produce.QUEUE.In_Check(action);
                                }
                                else
                                {
                                    ShowWarmForm("本站無複測buffer,勿給複測信號！");
                                    Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "本站無複測buffer-無法給複測信號");
                                }

                            }

                            else if (ChoiceStatus == 8)//放板到治具
                            {
                                Log.AddMainLog("[" + sStationNum + "] 號治具,[" + Produce.UserJob + "] " + Produce.LoginName + " 手動操作，ATS測試");
                                Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "ATS測試");
                                status = Status.Testing;
                                SendParameter("CtoT_placeDUTOK");
                            }
                            bmanualstatus = false;
                        }
                        else
                        {
                            ShowWarmForm("已有信號或手臂動作未完成！");
                            Log.AddManualLog("測試狀態", "[" + sStationNum + "] 更改手臂信號", this.status.ToString(), "已有信號或手臂動作未完成-無法更改");
                        }
                    }
                }
                else
                {

                    //AddURServerLog("當前沒有登錄帳號，無法手動操作");
                }
                Produce.bManualChangeStatus = false;
            }

        }

        private void checkBox2_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox2.Checked)
            {
                this.bWarning = false;
            }
            else
            {
                this.bWarning = true;
            }
        }

        public void ConnectServer()
        {
            try
            {
                bmanualstop = false;
                ClientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                RemoteEP = new IPEndPoint(IPAddress.Parse(IP), Port);
                ClientSocket.Connect(RemoteEP);
                if (ClientSocket.Connected)
                {
                    ReceiveServerThread = new Thread(new ThreadStart(ReceiveServer));
                    ReceiveServerThread.Start();
                    SendServerThread = new Thread(new ThreadStart(SendServer));
                    SendServerThread.Start();
                    HeartBeatThread = new Thread(new ThreadStart(HeartBeat));
                    HeartBeatThread.Start();
                }
            }
            catch (Exception)
            {
                this.DisConnectServer();
            }
        }
        public void DisConnectServer()
        {
            bmanualstop = true;

            //if (ClientSocket.Connected)
            //{


            if (ReceiveServerThread != null && ReceiveServerThread.IsAlive)
            {
                ReceiveServerThread.Abort();
            }
            if (SendServerThread != null && SendServerThread.IsAlive)
            {
                SendServerThread.Abort();
            }
            if (HeartBeatThread != null && HeartBeatThread.IsAlive)
            {
                HeartBeatThread.Abort();
            }
            //this.ClientSocket.Shutdown(SocketShutdown.Both);
            try
            {
                this.ClientSocket.Disconnect(false);
            }
            catch (Exception ex1) { };
            try
            {
                this.ClientSocket.Close();
                this.ClientSocket.Dispose();
                this.ClientSocket = null;
            }
            catch (Exception ex2) { };
            //}
        }

        public bool IsConnected()
        {
            try
            {
                return ClientSocket.Connected;
            }
            catch (Exception ex)
            {
                return false;
            }
        }

        public void ReceiveServer()
        {
            StringBuilder sb = new StringBuilder();
            string terminateString = "_CEND";
            int receiveBufferSize = 1024;
            byte[] buffer = new byte[receiveBufferSize];  //buffer大小，此处为1024
            int receivedSize = 0;
            string rawMsg = "";
            int rnFixLength = terminateString.Length;   //这个是指消息结束符的长度，此处为\r\n

            try
            {

                while (this.ClientSocket.Connected)
                {
                    if (bmanualstop)
                    {
                        break;
                    }
                    receivedSize = this.ClientSocket.Receive(buffer);
                    rawMsg = System.Text.Encoding.UTF8.GetString(buffer, 0, receivedSize);
                    for (int i = 0; i < rawMsg.Length; )               //遍历接收到的整个buffer文本
                    {
                        if (i <= rawMsg.Length - rnFixLength)
                        {
                            if (rawMsg.Substring(i, rnFixLength) != terminateString)//非消息结束符，则加入sb
                            {
                                sb.Append(rawMsg[i]);
                                i++;
                            }
                            else
                            {

                                string MyReceive = sb.ToString();
                                if (!MyReceive.Contains("fix_"))
                                {
                                    Log.AddMainLog("[治具 " + sStationNum + "] " + "Receive From ATS:" + MyReceive);
                                }
                                bool bstopused = false;


                                #region PASS結果
                                if (MyReceive.Contains("TtoC_resultPass"))
                                {
                                    NGWarningTimes = 0;
                                    //Program.form1.bRun = true;
                                    SetTextBoxCallback(textBox_LianxuNG, NGWarningTimes.ToString());

                                    if (bGoldenSample && bPutGolden)
                                    {
                                        bAlreadyTestGolden = true;
                                        Log.AddMainLog("[治具 " + sStationNum + "] 標準件測試完成");
                                    }
                                    else
                                    {
                                        if (bTXPowerTest)
                                        {
                                            bAlreadyTestTXPower = true;
                                            Log.AddMainLog("[治具 " + sStationNum + "] TXPower首件測試完成");
                                        }

                                        Produce.PassDUTCount++;
                                        this.PassCount++;
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Pass", PassCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Total", total.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Pass", Produce.PassDUTCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Total", Produce.TotalDUTCount.ToString());
                                    }
                                    this.status = TestUI.Status.Pass;

                                    action.StationNumber = sStationNum;
                                    action.robotCmd = Produce.RobotCMD.PASS;
                                    action.UserControlStatus = TestUI.Status.Testing;
                                    action.ResponeServerMsg = "CtoT_placeDUTOK";
                                    Produce.QUEUE.In_Check(action);

                                    if (Produce.bControlFixture)
                                    {
                                        this.SendFixOpen();
                                    }
                                }

                                #endregion

                                #region NG 結果
                                else if (MyReceive.Contains("TtoC_resultNG"))
                                {
                                    //Program.form1.bRun = true
                                    if (bGoldenSample && bPutGolden)
                                    {
                                        bAlreadyTestGolden = true;
                                        Log.AddMainLog("[治具 " + sStationNum + "] 標準件測試完成");
                                    }
                                    else
                                    {
                                        if (bTXPowerTest)
                                        {
                                            bAlreadyTestTXPower = true;
                                            Log.AddMainLog("[治具 " + sStationNum + "] TXPower首件測試完成");
                                        }
                                        NGWarningTimes++;
                                        SetTextBoxCallback(textBox_LianxuNG, NGWarningTimes.ToString());
                                        Produce.NGDUTCount++;
                                        this.NGCount++;
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "NG", NGCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Total", total.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "NG", Produce.NGDUTCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Total", Produce.TotalDUTCount.ToString());
                                    }
                                    try
                                    {
                                        this.NGItem = MyReceive.Split('+')[1].Trim().Replace(",", "");
                                    }
                                    catch (Exception ex)
                                    {
                                        this.NGItem = "UnKnown";
                                    }
                                    try
                                    {
                                        this.NGValue = MyReceive.Split('+')[2].Trim().Replace(",", "");
                                    }
                                    catch (Exception ex1)
                                    {
                                        this.NGValue = "UnKnown";
                                    }

                                    this.status = TestUI.Status.NG;

                                    if (NGWarningTimes == Produce.LianxuWarningCount)
                                    {
                                        if (bWarning)
                                        {
                                            //報警
                                            Produce.bNeedBaoJing = true;
                                            Produce.MainWarning = Produce.Station.Name[StationNumber].ToString() + "站 " + sStationNum + "號治具" + "連續" + NGWarningTimes.ToString() + "次不良";
                                            Log.AddExceptionLog(SN, "連續" + NGWarningTimes.ToString() + "次不良", StationNumber);
                                            Log.AddMainLog("[治具 " + sStationNum + "] 連續" + NGWarningTimes.ToString() + "次不良");
                                            if (Produce.WarningStopUse)
                                            {
                                                bstopused = true;
                                                Log.AddMainLog("[治具 " + sStationNum + "] 停用該治具");
                                                SetCheckBox(checkBox_Used, false);
                                            }
                                        }

                                        NGWarningTimes = 0;
                                    }

                                    if (!bstopused)
                                    {
                                        action.StationNumber = sStationNum;
                                        action.robotCmd = Produce.RobotCMD.NG;
                                        action.UserControlStatus = TestUI.Status.Testing;
                                        action.ResponeServerMsg = "CtoT_placeDUTOK";

                                        Produce.QUEUE.In_Check(action);
                                    }

                                    if (Produce.bControlFixture)
                                    {
                                        this.SendFixOpen();
                                    }
                                }
                                #endregion

                                #region Warning 結果
                                else if (MyReceive.Contains("TtoC_resultWarning"))
                                {


                                    //Program.form1.bRun = true;
                                    try
                                    {
                                        this.WarningMSG = MyReceive.Split('+')[1].Trim();
                                    }
                                    catch (Exception ex2)
                                    {
                                        this.WarningMSG = "Unknown";
                                    }

                                    if (bGoldenSample && bPutGolden)
                                    {
                                        bAlreadyTestGolden = true;
                                        Log.AddMainLog("[治具 " + sStationNum + "] 標準件測試完成");
                                    }
                                    else if (WarningMSG.Contains("抽測"))
                                    {
                                        bAlreadyTestTXPower = true;
                                        Log.AddMainLog("[治具 " + sStationNum + "] 抽測產品");
                                    }
                                    else
                                    {
                                        if (bTXPowerTest)
                                        {
                                            Log.AddMainLog("[治具 " + sStationNum + "] TXPower首件測試完成");
                                        }
                                        Produce.WarningDUTCount++;
                                        this.WarningCount++;
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Warning", WarningCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Total", total.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Warning", Produce.WarningDUTCount.ToString());
                                        INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Total", Produce.TotalDUTCount.ToString());
                                        NGWarningTimes++;
                                        SetTextBoxCallback(textBox_LianxuNG, NGWarningTimes.ToString());
                                    }

                                    this.status = TestUI.Status.Warning;

                                    if (NGWarningTimes == Produce.LianxuWarningCount)
                                    {
                                        if (bWarning)
                                        {
                                            //報警
                                            Produce.bNeedBaoJing = true;
                                            Produce.MainWarning = Produce.Station.Name[StationNumber].ToString() + "站 " + sStationNum + "號治具" + "連續" + NGWarningTimes.ToString() + "次不良";
                                            Log.AddExceptionLog(SN, "連續" + NGWarningTimes.ToString() + "次不良", StationNumber);
                                            Log.AddMainLog("[Station " + sStationNum + "] 連續" + NGWarningTimes.ToString() + "次不良");
                                            if (Produce.WarningStopUse)
                                            {
                                                bstopused = true;
                                                Log.AddMainLog("[治具 " + sStationNum + "] 停用該治具");
                                                SetCheckBox(checkBox_Used, false);
                                            }
                                        }

                                        NGWarningTimes = 0;
                                    }


                                    if (!bstopused)
                                    {
                                        action.StationNumber = sStationNum;
                                        if (WarningMSG.Contains("抽測"))
                                        {
                                            action.robotCmd = Produce.RobotCMD.ChouJian;
                                        }
                                        else
                                        {
                                            action.robotCmd = Produce.RobotCMD.NG;
                                        }
                                        action.UserControlStatus = TestUI.Status.Testing;
                                        action.ResponeServerMsg = "CtoT_placeDUTOK";

                                        Produce.QUEUE.In_Check(action);
                                    }

                                    if (Produce.bControlFixture)
                                    {
                                        this.SendFixOpen();
                                    }
                                }
                                #endregion

                                #region Retest 結果
                                else if (MyReceive.Contains("TtoC_resultRetest"))
                                {


                                    //Program.form1.bRun = true;
                                    try
                                    {
                                        this.WarningMSG = MyReceive.Split('+')[1].Trim();
                                    }
                                    catch (Exception ex2)
                                    {
                                        this.WarningMSG = "Unknown";
                                    }


                                    if (bGoldenSample && bPutGolden)
                                    {
                                        bAlreadyTestGolden = true;
                                        Log.AddMainLog("[Station " + sStationNum + "] 標準件測試完成");
                                    }
                                    else
                                    {
                                        //if (bTXPowerTest)
                                        //{
                                        //    Log.AddMainLog("[治具 " + sStationNum + "] TXPower首件測試完成");
                                        //}
                                        NGWarningTimes++;
                                        SetTextBoxCallback(textBox_LianxuNG, NGWarningTimes.ToString());
                                    }

                                    this.status = TestUI.Status.Retest;

                                    if (NGWarningTimes == Produce.LianxuWarningCount)
                                    {
                                        if (bWarning)
                                        {
                                            //報警
                                            Produce.bNeedBaoJing = true;
                                            Produce.MainWarning = Produce.Station.Name[StationNumber].ToString() + "站 " + sStationNum + "號治具" + "連續" + NGWarningTimes.ToString() + "次不良";
                                            Log.AddExceptionLog(SN, "連續" + NGWarningTimes.ToString() + "次不良", StationNumber);
                                            Log.AddMainLog("[Station " + sStationNum + "] 連續" + NGWarningTimes.ToString() + "次不良");
                                            if (Produce.WarningStopUse)
                                            {
                                                bstopused = true;
                                                Log.AddMainLog("[治具 " + sStationNum + "] 停用該治具");
                                                SetCheckBox(checkBox_Used, false);
                                            }
                                        }

                                        NGWarningTimes = 0;
                                    }
                                    if (!bstopused)
                                    {
                                        action.StationNumber = sStationNum;
                                        action.robotCmd = Produce.RobotCMD.Retest;
                                        action.UserControlStatus = TestUI.Status.Testing;
                                        action.ResponeServerMsg = "CtoT_placeDUTOK";

                                        Produce.QUEUE.In_Check(action);
                                    }

                                    if (Produce.bControlFixture)
                                    {
                                        this.SendFixOpen();
                                    }
                                }
                                #endregion

                                #region 條碼信息
                                else if (MyReceive.Contains("TtoC_barcode"))
                                {
                                    Barcode = MyReceive.Split('+')[1].Trim();
                                    if (Barcode.IndexOf("Z") == 7)
                                    {
                                        bGoldenSampleBarcode = true;
                                    }
                                    else
                                    {
                                        bGoldenSampleBarcode = true;//j73wei gai golden sn
                                    }

                                    this.SN = Barcode;


                                }
                                #endregion

                                if (MyReceive.Contains("fix_error"))
                                {
                                    this.fix_status = FixStatus.Error;
                                }
                                else if (MyReceive.Contains("fix_open"))
                                {
                                    this.fix_status = FixStatus.Open;
                                }
                                else if (MyReceive.Contains("fix_close"))
                                {
                                    this.fix_status = FixStatus.Close;
                                }

                                sb.Remove(0, sb.Length);
                                i += rnFixLength;
                            }

                        }
                        else
                        {
                            sb.Append(rawMsg[i]);
                            i++;
                        }
                    }
                    Thread.Sleep(100);
                }


            }
            catch (Exception e)
            {
                if (!e.ToString().Contains("ThreadAbortException"))
                {
                    //Log.AddExceptionLog(sStationName + sStationNum, "接收ATS時 異常:" + e.Message);
                }


            }

        }

        string buffQ_status = "Empty";
        public void SendServer()
        {
            try
            {
                while (true)
                {
                    if (this.ClientSocket.Connected)
                    {
                        if (bmanualstop)
                        {
                            break;
                        }

                        if (ServerQ.Out(ref msg) && msg != null)
                        {
                            this.SendCmd(msg.ToString());
                        }
                    }
                    if (!ServerBuffQ.IsEmpty())
                    {
                        if (buffQ_status == "Empty")
                        {
                            buffQ_status = "NotEmpty";
                        }
                    }
                    else
                    {
                        if (buffQ_status == "NotEmpty")
                        {
                            buffQ_status = "Empty";
                        }
                    }
                    if (!ServerQ.IsFull() && ServerBuffQ.Out(ref msg) && msg != null)
                    {
                        this.ServerQ.In(msg.ToString());
                    }

                    Thread.Sleep(10);
                }
            }
            catch (Exception e)
            {
                if (!e.ToString().Contains("ThreadAbortException"))
                {
                    //Log.AddExceptionLog(sStationName + sStationNum, "Send to ATS Exception:" + e.Message);
                }
            }
        }
        public void HeartBeat()
        {
            try
            {
                while (this.ClientSocket.Connected)
                {
                    if (bmanualstop)
                    {
                        break;
                    }
                    Thread.Sleep(100);      //delay時間不要太短，會造成隊列擁堵
                    if (!Produce.bControlFixture)
                        this.SendParameter("aaa");
                    else
                        this.SendParameter("fixstatus");
                }
            }
            catch (Exception e)
            {
                if (!e.ToString().Contains("ThreadAbortException"))
                {
                    //Log.AddExceptionLog(sStationName + sStationNum, "Heart Beat Exception:" + e.Message);
                }
            }
        }

        private string ParseDataToStr(byte[] data)
        {
            return Encoding.UTF8.GetString(data);
        }
        private byte[] ParseStrToData(string str)
        {
            return Encoding.UTF8.GetBytes(str);
        }
        public void SendParameter(string Parameter)
        {
            if (!ServerQ.In(Parameter))
            {
                ServerBuffQ.In(Parameter);
            }
        }
        private void SendCmd(string cmd)
        {
            try
            {
                if (this.ClientSocket.Connected)
                {
                    if (!cmd.Contains("aaa") && !cmd.Contains("fixstatus"))
                    {
                        Log.AddMainLog("[Station" + sStationNum + "] Send to ATS:" + cmd);
                    }

                    this.ClientSocket.Send(ParseStrToData(cmd + "_CEND"));
                    if (cmd == "CtoT_placeDUTOK")
                    {
                        this.Barcode = "";
                    }
                }
            }
            catch (Exception e)
            {
                //Log.AddExceptionLog(sStationNum, "Send to ATS Fail:" + e.Message);
            }
        }
        private bool bcloseerror = false;
        private bool bAlreadyclose;
        private bool bFirstUsed = false;
        private bool bFixclosed = false;
        private bool bfixwarn = false;
        public void ATSConnect()
        {

            Thread.Sleep(1000);

            while (true)
            {

                if (checkBox_Used.Checked)
                {

                    bAlreadyclose = false;
                    if (!bFirstUsed)
                    {
                        bFirstUsed = true;
                    }

                    if (!IsConnected())
                    {
                        SetJianBianPanelColor(panel_connectStatus, Color.Red, Color.FromArgb(64, 0, 0));
                        ConnectServer();
                        this.fix_status = FixStatus.None;
                    }
                    else
                    {
                        SetJianBianPanelColor(panel_connectStatus, Color.Lime, Color.FromArgb(0, 64, 0));

                        if (Robots.Robot.RobotDoingStation.IndexOf(StationNumber) != -1)
                        {
                            if (Produce.RobotDoneOver_ByStation[StationNumber - 1])
                            {

                                #region Check Fix close
                                if (Produce.bControlFixture)
                                {
                                    if (!bFixclosed)
                                    {
                                        bFixclosed = true;
                                        SendFixClose();
                                    }


                                    if (fix_status == TestUI.FixStatus.Close)
                                    {
                                        Log.AddMainLog("ATS[" + sStationNum + "] Fixture is close!");
                                        bcloseerror = false;
                                    }

                                    if (fix_status == TestUI.FixStatus.Error)
                                    {
                                        if (!bfixwarn)
                                        {
                                            bfixwarn = true;
                                            Log.AddMainLog("ATS[" + sStationNum + "] Fixture Status Error!");
                                            Produce.MainWarning = sStationNum + "號治具關閉異常";
                                            Log.AddExceptionLog(SN, "治具關閉異常", StationNumber);
                                            bcloseerror = true;
                                        }
                                    }
                                    if (fix_status == TestUI.FixStatus.None)
                                    {
                                        if (!bfixwarn)
                                        {
                                            bfixwarn = true;
                                            Log.AddMainLog("ATS[" + sStationNum + "] Fixture Not Connected!");
                                            Produce.MainWarning = sStationNum + "號治具未連接";
                                            bcloseerror = true;
                                            Log.AddExceptionLog(SN, "治具未連接-無法確認是否關閉", StationNumber);
                                        }
                                    }


                                }
                                #endregion

                                if (!bcloseerror)
                                {
                                    if (action.ResponeServerMsg != "MANUAL_CLEAR_NOSINGLE" && action.ResponeServerMsg != "MANUAL_PUT_NOSINGLE")
                                    {
                                        SendParameter(DUTTestTime.ToString() + "," + action.ResponeServerMsg);
                                    }
                                    status = action.UserControlStatus;
                                    Produce.RobotDoneOver_ByStation[StationNumber - 1] = false;
                                    Robots.Robot.RobotDoingStation.Remove(StationNumber);
                                    bFixclosed = false;
                                }
                            }
                        }

                    }

                    try
                    {
                        if (!Produce.bShowATS[StationNumber - 1])
                        {
                            SetCheckBox(checkBox_Used, false);
                            SetVisible(false);
                            Produce.yulans.SetStation(StationNumber, Color.White);
                        }
                    }
                    catch (Exception ex)
                    {

                    }

                }
                else
                {

                    if (bFirstUsed && !bAlreadyclose)
                    {
                        bAlreadyclose = true;
                        if (Robots.Robot.RobotDoingStation.IndexOf(StationNumber) != -1 && !Produce.RobotDoneOver_ByStation[StationNumber - 1])
                        {
                            Log.AddMainLog("手臂正在處理[" + sStationNum + "]號治具，停止使用不清除信號");
                        }
                        else
                        {

                            Log.AddMainLog("[" + sStationNum + "]號治具停止使用，清除信號");
                            Produce.QUEUE.Delete(sStationNum);

                            if (IsConnected())
                            {
                                DisConnectServer();
                            }
                        }

                        SetJianBianPanelColor(panel_connectStatus, Color.LightGray, Color.DarkGray);
                        this.fix_status = FixStatus.None;

                    }

                    try
                    {
                        if (!Produce.bShowATS[StationNumber - 1])
                        {
                            SetVisible(false);
                            Produce.yulans.SetStation(StationNumber, Color.White);
                        }
                        else
                        {
                            SetVisible(true);
                            Produce.yulans.SetStation(StationNumber, Color.Gray);
                        }
                    }
                    catch (Exception ex)
                    { }
                }

                Thread.Sleep(10);
            }

        }

        public void SendFixOpen()
        {
            Log.AddMainLog("Send to ATS:Open Fixture");
            SendParameter("f_open_CEND");
        }

        public void SendFixClose()
        {
            Log.AddMainLog("Send to ATS:Close Fixture");
            SendParameter("f_close_CEND");
        }

        #region  控件委託

        delegate void dSetVisible(bool bVisible);
        public void SetVisible(bool bVisible)
        {
            try
            {
                if (this.InvokeRequired)
                {
                    dSetVisible d = new dSetVisible(SetVisible);
                    this.Invoke(d, new object[] { bVisible });
                }
                else
                {
                    if (this.Visible != bVisible)
                    {
                        this.Visible = bVisible;
                    }
                }
            }
            catch (Exception ex)
            { }
        }


        delegate void dSetTextBoxCallback(TextBox textbox, string msg);
        public void SetTextBoxCallback(TextBox textbox, string msg)
        {
            if (textbox.InvokeRequired)
            {
                dSetTextBoxCallback d = new dSetTextBoxCallback(SetTextBoxCallback);
                textbox.Invoke(d, new object[] { textbox, msg });
            }
            else
            {
                textbox.Text = msg;

            }
        }

        delegate void dSetLabelTextCallback(Control label, string msg, Color Backcolor);
        private void SetLabelTextCallback(Control label, string msg, Color Backcolor)
        {
            if (label.InvokeRequired)
            {
                dSetLabelTextCallback d = new dSetLabelTextCallback(SetLabelTextCallback);
                label.Invoke(d, new object[] { label, msg, Backcolor });
            }
            else
            {
                label.Text = msg;
                if (label.BackColor != Backcolor)
                {
                    label.BackColor = Backcolor;
                }
                label.Refresh();
                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }




        delegate void dSetPanelColorback(Panel panel, Color Backcolor);
        public void SetPanelColorback(Panel panel, Color Backcolor)
        {
            if (panel.InvokeRequired)
            {
                dSetPanelColorback d = new dSetPanelColorback(SetPanelColorback);
                panel.Invoke(d, new object[] { panel, Backcolor });
            }
            else
            {

                if (panel.BackColor != Backcolor)
                {
                    panel.BackColor = Backcolor;
                    panel.Refresh();
                }

                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }

        delegate void dSetRadioButton(RadioButton rbt, bool bChecked);
        public void SetRadioButton(RadioButton rbt, bool bChecked)
        {
            if (rbt.InvokeRequired)
            {
                dSetRadioButton d = new dSetRadioButton(SetRadioButton);
                rbt.Invoke(d, new object[] { rbt, bChecked });
            }
            else
            {
                rbt.Checked = bChecked;
            }
        }

        delegate void dSetJianBianPanelColor(JianBianPanel panel, Color centercolor, Color surroundcolor);
        public void SetJianBianPanelColor(JianBianPanel panel, Color centercolor, Color surroundcolor)
        {
            if (panel.InvokeRequired)
            {
                dSetJianBianPanelColor d = new dSetJianBianPanelColor(SetJianBianPanelColor);
                panel.Invoke(d, new object[] { panel, centercolor, surroundcolor });
            }
            else
            {

                if (panel.CenterColor != centercolor || panel.SurroundColor != surroundcolor)
                {
                    panel.CenterColor = centercolor;
                    panel.SurroundColor = surroundcolor;
                    panel.Refresh();
                }

                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }

        delegate void dSetJianBianButtonColor(JianBianButton button, string text, Color centercolor, Color surroundcolor);
        public void SetJianBianButtonColor(JianBianButton button, string text, Color centercolor, Color surroundcolor)
        {
            if (button.InvokeRequired)
            {
                dSetJianBianButtonColor d = new dSetJianBianButtonColor(SetJianBianButtonColor);
                button.Invoke(d, new object[] { button, text, centercolor, surroundcolor });
            }
            else
            {
                button.Text = text;
                if (button.CenterColor != centercolor || button.SurroundColor != surroundcolor)
                {
                    button.CenterColor = centercolor;
                    button.SurroundColor = surroundcolor;
                    button.Refresh();

                }

                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }


        delegate void dSetProgressBar(XpProgressBar ps, int nvalue);
        public void SetProgressBar(XpProgressBar ps, int nvalue)
        {
            if (ps.InvokeRequired)
            {
                dSetProgressBar d = new dSetProgressBar(SetProgressBar);
                ps.Invoke(d, new object[] { ps, nvalue });
            }
            else
            {
                ps.Position = nvalue;
                ps.Refresh();
                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }

        delegate void dSetProgressBarText(XpProgressBar ps, string text);
        public void SetProgressBarText(XpProgressBar ps, string text)
        {
            if (ps.InvokeRequired)
            {
                dSetProgressBarText d = new dSetProgressBarText(SetProgressBarText);
                ps.Invoke(d, new object[] { ps, text });
            }
            else
            {
                ps.Text = text;
                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }

        delegate void dSetCheckBox(CheckBox cb, bool bcheck);
        public void SetCheckBox(CheckBox cb, bool bcheck)
        {
            if (cb.InvokeRequired)
            {
                dSetCheckBox d = new dSetCheckBox(SetCheckBox);
                cb.Invoke(d, new object[] { cb, bcheck });
            }
            else
            {
                cb.Checked = bcheck;
                this.Refresh();
                //label.Refresh();
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }
        #endregion
    }
}
