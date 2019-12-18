using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using AutoMationTest.UI;
using System.Threading;
using System.Collections;
using AutoMationTest.Function;
using AutoMationTest.Robots;
using System.Net;
using AutoMationTest.IO;
using Microsoft.VisualBasic.PowerPacks;
using System.IO;
using System.Diagnostics;

namespace RobotMainForm
{
    public partial class MainForm : Form
    {
        public MainForm()
        {
            InitializeComponent();
            this.pbox_Remote.MouseWheel += new MouseEventHandler(pbox_Remote_MouseWheel);
            bt_key.PreviewKeyDown += new PreviewKeyDownEventHandler(pbox_Remote_PreviewKeyDown);
            //bt_key.KeyDown += new KeyEventHandler(bt_key_KeyDown);
            bt_key.KeyUp += new KeyEventHandler(bt_key_KeyUp);
        }



        private void MainForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (File.Exists(Application.StartupPath + "\\LAST.csv"))
                File.Delete(Application.StartupPath + "\\LAST.csv");
            File.AppendAllText(Application.StartupPath + "\\LAST.csv", "有無信號,信號,站別,治具,測試狀態\r\n");

            for (int j = 0; j < Produce.QUEUE.GetQueueLength(); j++)
            {
                File.AppendAllText(Application.StartupPath + "\\LAST.csv", "有," + Produce.QUEUE[j].robotCmd.ToString() + "," + allatsui1.ATS[Convert.ToInt32(Produce.QUEUE[j].StationNumber) - 1].StationName.Text + "," + Produce.QUEUE[j].StationNumber + "," + allatsui1.ATS[Convert.ToInt32(Produce.QUEUE[j].StationNumber) - 1].status.ToString() + "\r\n");
            }

            for (int i = 0; i < Produce.Station.Count; i++)
            {
                if (!Produce.QUEUE.Exist(Convert.ToString(i + 1)))
                {

                    if (allatsui1.ATS[i].checkBox_Used.Checked)
                    {
                        File.AppendAllText(Application.StartupPath + "\\LAST.csv", "無,," + allatsui1.ATS[i].StationName.Text + "," + allatsui1.ATS[i].StationNumber.ToString() + "," + allatsui1.ATS[i].status.ToString() + "\r\n");
                    }
                    else
                    {
                        File.AppendAllText(Application.StartupPath + "\\LAST.csv", "無,," + allatsui1.ATS[i].StationName.Text + "," + allatsui1.ATS[i].StationNumber.ToString() + ",未使用\r\n");
                    }

                }
            }



            Environment.Exit(0);
        }

        Thread detectwarnThread;
        Thread MainThread;
        Thread IOThread;
        Thread GetRobotThread;
        Thread BaojingThread;
        Thread FixStatusThead;
        RemoteControl rm = new RemoteControl();
        bool bYouLiao = false;
        bool bGoHomeAlready = false;
        bool bRobotGetLiao = false;
        bool bGoldenYouLiao = false;
        bool bGoldentest = false;
        public bool bPaused = true;
        public int DoingGroup = 0;
        private bool bRobotconnected = false;
        private bool bRobotPaused = false;
        bool bRobotwarned = false;
        bool bSafeDoor = false;
        bool bDoorOpend = false;
        bool bNGFull = false;
        bool bNGFullWarned = false;
        private string roborerror = "";
        private bool bBaojingEnd = false;
        private bool bSkipBaoJing = false;
        private bool bQuxiaoBaojing = false;
        private bool bskiptest = false;
        private string sWarning = "";
        public TestMode _testmode = TestMode.Normal;
        bool bQingLiao = false;
        public MyIO _myio;
        bool bGRRTest = false;
        bool fisrt_run = false;


        Hashtable[] hs_fixtestcount;
        Hashtable[] hs_fixtestloopcount;
        ArrayList grrdutsn;
        int nGRRTotalCount = 0;
        int nGRRAlreadyCount = 0;
        //int nGRRNottestCount = 0;

        bool bAlreadyQingLiaoEnd = false;

        public enum TestMode
        {
            Normal,
            QingLiao,
        }

        Point remotepoint;
        bool bDisConnectRemote = false;
        IPAddress remoteip;

        DateTime beginTime;
        int localX = 1;
        int localY = 6;
        bool badd = false;
        YuLanForm godenform;
        ArrayList GroupArray = new ArrayList();
        ArrayList testlist;
        ArrayList goldentestlist;
        NormalBuffer[] WaitBuffer;

        string SelectFixStation = "";
        string GoldenSampleStaion = "";
        bool bshowio = false;
        bool bshowtouliao = false;
        bool bshowpasszone = false;
        bool bshowngzone = false;
        bool bshowfixstatus = false;
        bool pctimeover = false;
        bool boverwarned = false;
        bool bhaocaiwarned = false;
        double lasttotaldut;
        double lastpassdut;

        private void timer1_Tick(object sender, EventArgs e)
        {
            //if (lb_WarnMSG.Location.X == 1)
            //{
            //    badd = true;
            //}

            if (sWarning != "")
            {
                localX = bt_clearwarning.Width;

            }
            else
            {

                if (lb_WarnMSG.Location.X > panel4.Width - 6)
                {
                    //badd = false;
                    localX = 0 - lb_WarnMSG.Width + bt_clearwarning.Width;
                }

                //if (badd)
                //{
                localX++;
                //}
                //else
                //{
                //    localX--;
                //}
            }

            lb_WarnMSG.Location = new Point(localX, localY);
            lb_WarnMSG.Refresh();
        }

        private void numericUpDown1_ValueChanged(object sender, EventArgs e)
        {
            int value = Convert.ToInt16(((NumericUpDown)sender).Value);

            if (value == 0)
            {
                ((NumericUpDown)sender).Value = 1;
                value = 1;
            }

            switch (((NumericUpDown)sender).Name)
            {
                case "num_ATS":
                    allatsui1.ATSCountPerColumn = value;
                    INI.WriteINI(Application.StartupPath + "\\Data", "UI", "Station", "ATSPerColumn", value.ToString());
                    break;
                case "num_Row":
                    allatsui1.RowInterval = value;
                    INI.WriteINI(Application.StartupPath + "\\Data", "UI", "Station", "RowInterval", value.ToString());
                    break;
                case "num_Column":
                    allatsui1.ColumnInterval = value;
                    INI.WriteINI(Application.StartupPath + "\\Data", "UI", "Station", "ColumnInterval", value.ToString());
                    break;
            }

        }
        private void InitialYuLan()
        {
            Produce.yulans = new YuLanForm();
            Produce.yulans.Location = new Point(0, 0);
            Produce.yulans.InitialYuLan();

            panel_yulan.Controls.Add(Produce.yulans);

        }

        //private void InitialGroup()
        //{
        //    for (int p = 0; p < Produce.Station.NameAll.Length; p++)
        //    {
        //        int Group = Convert.ToInt16(Produce.Station.NameAll[p].ToString());
        //        if (!GroupArray.Contains(Group))
        //        {
        //            GroupArray.Add(Group);
        //        }
        //    }
        //}

        private void InitialUI()
        {
            int atspercol = Convert.ToInt16(INI.ReadINI(Application.StartupPath + "\\Data", "UI", "Station", "ATSPerColumn", "4"));
            int rowinterval = Convert.ToInt16(INI.ReadINI(Application.StartupPath + "\\Data", "UI", "Station", "RowInterval", "20"));
            int colinterval = Convert.ToInt16(INI.ReadINI(Application.StartupPath + "\\Data", "UI", "Station", "ColumnInterval", "20"));

            num_ATS.Value = atspercol;
            num_Row.Value = rowinterval;
            num_Column.Value = colinterval;

            allatsui1.ATSCountPerColumn = atspercol;
            allatsui1.RowInterval = rowinterval;
            allatsui1.ColumnInterval = colinterval;

            for (int i = 0; i < allatsui1.tb1.TabCount; i++)
            {
                allatsui1.tb1.SelectedIndex = i;
            }

            allatsui1.tb1.SelectedIndex = 0;
            if (GoldenSampleStaion != "")
            {
                if (!Produce.Station.NameAll.Contains(GoldenSampleStaion))
                {
                    GoldenSampleStaion = Produce.Station.NameAll[0].ToString();
                }

            }
            else
            {
                GoldenSampleStaion = Produce.Station.NameAll[0].ToString();
            }

        }

        private void InitialStationSet()
        {

            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                listBox1.Items.Add(Produce.Station.NameAll[p].ToString());
                int Group = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[p].ToString()]);
                if (!GroupArray.Contains(Group))
                {
                    GroupArray.Add(Group);
                }
            }

            listBox1.SelectedIndex = 0;
        }

        private void MainForm_Load(object sender, EventArgs e)
        {
         

            InitialUI();

            InitialYuLan();

            InitialStationSet();

            InitialRobot();

            InitialIO();

            Thread RunTimeThread = new Thread(new ThreadStart(RunTime));
            RunTimeThread.Start();

            detectwarnThread = new Thread(new ThreadStart(DetectException));
            detectwarnThread.Start();

            FixStatusThead = new Thread(new ThreadStart(CheckFixStatus));
            FixStatusThead.Start();


            MainThread = new Thread(new ThreadStart(Test));
            MainThread.Start();

            //Produce.bLoginOK = true;
            //Produce.UserLevel = 6;

        }

        private void CheckFixStatus()
        {
            while (true)
            {
                Thread.Sleep(100);

                try
                {
                    if (bshowfixstatus && SelectFixStation != "")
                    {
                        int[] fixlist = (int[])Produce.Station.NumberList[SelectFixStation];
                        for (int i = 0; i < fixlist.Length; i++)
                        {
                            string text = "";
                            switch (allatsui1.ATS[fixlist[i] - 1].fix_status)
                            {
                                case TestUI.FixStatus.None:
                                    text = "未連接";
                                    break;
                                case TestUI.FixStatus.Error:
                                    text = "異常";
                                    break;
                                case TestUI.FixStatus.Open:
                                    text = "Open";
                                    break;
                                case TestUI.FixStatus.Close:
                                    text = "Close";
                                    break;
                            }

                            ((FixtureControl)autoPanel_fixstatus.Controls[i]).ShowStatus(text);

                        }
                    }
                }
                catch (Exception ex)
                { }
            }
        }

        private void InitialRobot()
        {
            Produce.Epson = new Robot(Robot.RobotType.Epson);
            //Epson.Connect();


            GetRobotThread = new Thread(new ThreadStart(GetRobot));
            GetRobotThread.Start();

        }


        private void GetRobot()
        {

            while (true)
            {
                try
                {

                    if (Produce.Epson != null)
                    {
                        //MessageBox.Show(Robot.IsConnected.ToString());

                        if (Robot.IsConnected)
                        {
                            if (!bRobotconnected)
                            {
                                bRobotconnected = true;
                                SetJianBianPanelColor(robot_status, Color.Lime, Color.FromArgb(0, 64, 0));
                                Log.AddMainLog("手臂已連接!");
                            }


                        }
                        else
                        {

                            if (bRobotconnected)
                            {
                                bRobotconnected = false;
                                SetJianBianPanelColor(robot_status, Color.WhiteSmoke, Color.Black);
                                Log.AddMainLog("手臂已斷開!");
                            }
                        }
                    }
                    else
                    {
                        SetJianBianPanelColor(robot_status, Color.WhiteSmoke, Color.Black);
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Robot Error:" + ex.ToString());
                }

                Thread.Sleep(50);
            }
        }


        private void InitialIO()
        {
            _myio = new MyIO(MyIO.IOType.Epson);


            for (int j = 0; j < _myio.InputCount; j++)
            {
                string[] inmsg = _myio.InputList[j].ToString().Split(',');

                OvalShape ovs = new OvalShape();
                ShapeContainer st = new ShapeContainer();

                ovs.BackStyle = Microsoft.VisualBasic.PowerPacks.BackStyle.Opaque;
                ovs.BorderColor = System.Drawing.Color.Indigo;
                ovs.BorderWidth = 4;
                ovs.FillColor = System.Drawing.Color.Red;
                ovs.FillGradientColor = System.Drawing.Color.Gold;
                ovs.FillGradientStyle = Microsoft.VisualBasic.PowerPacks.FillGradientStyle.Central;
                ovs.FillStyle = Microsoft.VisualBasic.PowerPacks.FillStyle.Solid;
                ovs.Location = new System.Drawing.Point(59, 82);
                ovs.Size = new System.Drawing.Size(35, 35);
                ovs.Location = new Point(60, j * 62 + 24);

                st.Location = new Point(0, 0);
                st.Margin = new System.Windows.Forms.Padding(0);
                st.Shapes.AddRange(new Microsoft.VisualBasic.PowerPacks.Shape[] { ovs });
                st.Size = new System.Drawing.Size(290, 426);
                st.TabIndex = 0;
                st.TabStop = false;

                Label lb = new Label();
                lb.Text = inmsg[0];
                lb.AutoSize = true;
                lb.Location = new Point(120, j * 62 + 28);

                autoPanel_input.Controls.Add(st);
                autoPanel_input.Controls.Add(lb);
            }


            for (int i = 0; i < _myio.OutputCount; i++)
            {

                string[] outmsg = _myio.OutputList[i].ToString().Split(',');

                UserSwitch usw = new UserSwitch();
                usw.Tag = i + 1;
                usw.Location = new Point(50, i * 62 + 10);
                usw.Click += this.userswitch_click;

                Label lb = new Label();
                lb.Text = outmsg[0];
                lb.AutoSize = true;
                lb.Location = new Point(120, i * 62 + 28);

                autoPanel_output.Controls.Add(usw);
                autoPanel_output.Controls.Add(lb);
            }


            IOThread = new Thread(new ThreadStart(CheckIO));
            IOThread.Start();
        }

        private void CheckIO()
        {
            while (true)
            {
                Thread.Sleep(50);

                for (int j = 0; j < _myio.InputCount; j++)
                {
                    try
                    {
                        if (_myio.ReadInput(j) == 1)
                        {
                            if (_myio.InputList[j].ToString().Contains("安全門"))
                            {
                                bSafeDoor = false;
                            }

                            if (bshowio)
                                SetOVLED((OvalShape)(((ShapeContainer)autoPanel_input.Controls[j * 2]).Shapes.get_Item(0)), true);
                        }
                        else
                        {
                            if (_myio.InputList[j].ToString().Contains("安全門"))
                            {
                                if (_myio.ReadInput(j) == 0)
                                {
                                    bSafeDoor = true;
                                }
                            }

                            if (bshowio)
                                SetOVLED((OvalShape)(((ShapeContainer)autoPanel_input.Controls[j * 2]).Shapes.get_Item(0)), false);
                        }



                    }
                    catch (Exception ex) { }
                }

                for (int i = 0; i < _myio.OutputCount; i++)
                {
                    try
                    {
                        if (_myio.ReadOutput(i) == 1)
                        {
                            if (bshowio)
                                ((UserSwitch)autoPanel_output.Controls[i * 2]).SwitchStatus = true;
                        }
                        else
                        {
                            if (bshowio)
                                ((UserSwitch)autoPanel_output.Controls[i * 2]).SwitchStatus = false;
                        }
                    }
                    catch (Exception ex) { }
                }


                if (bshowtouliao)
                {
                    try
                    {
                        for (int g = 0; g < GroupArray.Count; g++)
                        {
                            int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[g].ToString()]);
                            for (int t = 0; t < count; t++)
                            {
                                int ioindex = Convert.ToInt32(Produce.Station.TouLiaoIO["g" + GroupArray[g].ToString() + "_" + Convert.ToString(t + 1)]);

                                if (_myio.ReadInput(ioindex - 1) == 1)
                                {
                                    ((NormalTouLiao)autoPanel_SetTouliao.Controls[t]).Status = NormalTouLiao.status.YouLiao;
                                }
                                else
                                {
                                    ((NormalTouLiao)autoPanel_SetTouliao.Controls[t]).Status = NormalTouLiao.status.Empty;
                                }
                            }
                        }

                    }
                    catch (Exception ex) { }
                }


                if (bshowpasszone)
                {
                    try
                    {
                        for (int g = 0; g < GroupArray.Count; g++)
                        {
                            int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[g].ToString()]);
                            for (int t = 0; t < count; t++)
                            {
                                int ioindex = Convert.ToInt32(Produce.Station.PassZoneIO["g" + GroupArray[g].ToString() + "_" + Convert.ToString(t + 1)]);

                                if (_myio.ReadInput(ioindex - 1) == 0)
                                {
                                    ((NormalTouLiao)autoPanel_setpass.Controls[t]).Status = NormalTouLiao.status.YouLiao;
                                }
                                else
                                {
                                    ((NormalTouLiao)autoPanel_setpass.Controls[t]).Status = NormalTouLiao.status.Empty;
                                }
                            }
                        }

                    }
                    catch (Exception ex) { }
                }

                if (bshowngzone)
                {
                    try
                    {
                        for (int g = 0; g < GroupArray.Count; g++)
                        {
                            int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[g].ToString()]);
                            for (int t = 0; t < count; t++)
                            {
                                int ioindex = Convert.ToInt32(Produce.Station.NGZoneIO["g" + GroupArray[g].ToString() + "_" + Convert.ToString(t + 1)]);

                                if (_myio.ReadInput(ioindex - 1) == 0)
                                {
                                    ((NormalTouLiao)autoPanel_setng.Controls[t]).Status = NormalTouLiao.status.YouLiao;
                                }
                                else
                                {
                                    ((NormalTouLiao)autoPanel_setng.Controls[t]).Status = NormalTouLiao.status.Empty;
                                }
                            }
                        }

                    }
                    catch (Exception ex) { }
                }
                try
                {
                    if (CheckNGZone())
                    {
                        bNGFull = false;
                    }
                    else
                    {
                        bNGFull = true;
                    }
                }
                catch (Exception ex)
                {
                    bNGFull = false;
                }

            }
        }

        private bool GetTouLiao(int group, ref int indexnume)
        {
            indexnume = 0;
            bool btouliaoyouliao = false;
            int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + group.ToString()]);
            try
            {
                for (int t = 0; t < count; t++)
                {
                    int ioindex = Convert.ToInt32(Produce.Station.TouLiaoIO["g" + group.ToString() + "_" + Convert.ToString(t + 1)]);

                    if (_myio.ReadInput(ioindex - 1) == 1)
                    {

                        int toucount = 0;
                        for (int j = 0; j < group; j++)
                        {
                            int gcount = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[j].ToString()]);
                            for (int k = 0; k < gcount; k++)
                            {
                                toucount++;
                            }

                        }

                        indexnume = t + 1 + toucount;
                        btouliaoyouliao = true;
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                btouliaoyouliao = false;
            }

            return btouliaoyouliao;
        }

        private bool GetGoldenLiao()
        {
            bool btgoldenyouliao = false;
            try
            {

                if (_myio.ReadInput(Produce.Station.GoldenIOindex - 1) == 1)
                {
                    btgoldenyouliao = true;
                }
            }
            catch (Exception ex)
            {
                btgoldenyouliao = false;
            }

            return btgoldenyouliao;
        }

        private bool GetPassZone(int group, ref int indexnume)
        {
            indexnume = 0;
            bool bcanput = false;
            int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + group.ToString()]);
            try
            {
                for (int t = 0; t < count; t++)
                {
                    int ioindex = Convert.ToInt32(Produce.Station.PassZoneIO["g" + group.ToString() + "_" + Convert.ToString(t + 1)]);

                    if (_myio.ReadInput(ioindex - 1) == 1)
                    {
                        int pscount = 0;
                        for (int j = 0; j < group; j++)
                        {
                            int gcount = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[j].ToString()]);
                            for (int k = 0; k < gcount; k++)
                            {
                                pscount++;
                            }

                        }
                        indexnume = t + 1 + pscount;
                        bcanput = true;
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                bcanput = false;
            }

            return bcanput;
        }

        private bool GetNGZone(int group, ref int indexnume)
        {
            indexnume = 0;
            bool bcanput = false;
            int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + group.ToString()]);
            try
            {
                for (int t = 0; t < count; t++)
                {
                    int ioindex = Convert.ToInt32(Produce.Station.NGZoneIO["g" + group.ToString() + "_" + Convert.ToString(t + 1)]);

                    if (_myio.ReadInput(ioindex - 1) == 1)
                    {
                        int ngcount = 0;
                        for (int j = 0; j < group; j++)
                        {
                            int gcount = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[j].ToString()]);
                            for (int k = 0; k < gcount; k++)
                            {
                                ngcount++;
                            }

                        }

                        indexnume = t + 1 + ngcount;
                        bcanput = true;
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                bcanput = false;
            }

            return bcanput;
        }

        private bool CheckNGZone()
        {
            bool bnotwarn = false;


            for (int j = 0; j < GroupArray.Count; j++)
            {
                int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[j].ToString()]);
                try
                {
                    for (int t = 0; t < count; t++)
                    {
                        int ioindex = Convert.ToInt32(Produce.Station.NGZoneIO["g" + GroupArray[j].ToString() + "_" + Convert.ToString(t + 1)]);

                        if (_myio.ReadInput(ioindex - 1) != 0)
                        {
                            bnotwarn = true;
                            break;
                        }
                    }
                }
                catch (Exception ex)
                {
                    bnotwarn = true;
                }

                if (bnotwarn)
                {
                    break;
                }

            }

            return bnotwarn;
        }


        private void button2_MouseDown(object sender, MouseEventArgs e)
        {
            int X = ((Button)sender).Location.X;
            int Y = ((Button)sender).Location.Y;
            ((Button)sender).Location = new Point(X, Y + 5);
        }

        private void button2_MouseUp(object sender, MouseEventArgs e)
        {
            int X = ((Button)sender).Location.X;
            int Y = ((Button)sender).Location.Y;
            ((Button)sender).Location = new Point(X, Y - 5);
        }

        private void bt_AddStation_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (Produce.QUEUE.GetQueueLength() != 0)
            {
                MessageBox.Show("存在站別信號時請不要更改站別！");
            }
            else
            {

                int index = listBox1.SelectedIndex;
                string selectstation = listBox1.SelectedItem.ToString();
                int count = listBox1.Items.Count;
                string name = "Station" + Convert.ToString(index + 2);
                listBox1.Items.Insert(index + 1, name);

                Log.AddManualLog("更改站別", "增加站別", "", name);

                string newstations = "";
                for (int i = 0; i < listBox1.Items.Count; i++)
                {
                    if (i < index + 1)
                    {
                        newstations += Produce.Station.NameAll[i] + ",";
                    }
                    else if (i == index + 1)
                    {
                        newstations += name + ",";
                    }
                    else
                    {
                        newstations += Produce.Station.NameAll[i - 1] + ",";
                    }

                }

                newstations = newstations.Substring(0, newstations.Length - 1);

                Produce.SetStationName(newstations);
                Produce.SetStationCount(name, 1);

                Produce.SetGroup(name, Convert.ToInt16(Produce.Station.Group[selectstation]));

                ChangeStation();

                listBox1.SelectedIndex = index + 1;
            }
        }

        private void bt_DeleteStation_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (Produce.QUEUE.GetQueueLength() != 0)
            {
                MessageBox.Show("存在站別信號時請不要更改站別！");
            }
            else
            {
                if (listBox1.Items.Count > 1)
                {
                    Log.AddManualLog("更改站別", "刪除站別", listBox1.SelectedItem.ToString(), "null");
                    int index = listBox1.SelectedIndex;

                    listBox1.Items.RemoveAt(index);

                    string newstations = "";
                    for (int i = 0; i < listBox1.Items.Count; i++)
                    {
                        newstations += listBox1.Items[i].ToString() + ",";
                    }

                    newstations = newstations.Substring(0, newstations.Length - 1);

                    Produce.SetStationName(newstations);

                    ChangeStation();

                    listBox1.SelectedIndex = index - 1;
                }


                //
            }
        }

        private void listBox1_SelectedIndexChanged(object sender, EventArgs e)
        {
            try
            {
                int index = listBox1.SelectedIndex;

                //int group = Convert.ToInt16(Produce.Station.Group[index]);
                //if (index > 0)
                //{

                //}
                //else
                //{
                //    nUpDown_Group.Minimum = 0;
                //}
                //nUpDown_Group.Maximum = index;

                autoPanel5.Controls.Clear();
                //autoPanel5.Refresh();
                string stationname = listBox1.SelectedItem.ToString();
                int[] List = (int[])Produce.Station.NumberList[stationname];
                string timeout = Produce.Station.TimeOut[stationname].ToString();

                tbox_stationname.Text = stationname;
                tBox_timeout.Text = timeout;

                for (int i = 0; i < List.Length; i++)
                {
                    FixtureSet fix = new FixtureSet();
                    fix.StationNumber = List[i];
                    try
                    {
                        fix.IP = allatsui1.ATS[List[i] - 1].IP;
                        fix.Port = allatsui1.ATS[List[i] - 1].Port;
                        //fix.TimeOut = allatsui1.ATS[List[i] - 1].TimeOut;
                    }
                    catch (Exception ex)
                    { }

                    fix.Location = new Point(30, 10 + 40 * i);
                    autoPanel5.Controls.Add(fix);
                }
            }
            catch (Exception)
            { }
        }

        private void button5_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (Produce.QUEUE.GetQueueLength() != 0)
            {
                MessageBox.Show("存在站別信號時請不要更改站別！");
            }
            else
            {
                int index = listBox1.SelectedIndex;
                string item = listBox1.SelectedItem.ToString();
                int Group = Convert.ToInt16(Produce.Station.Group[item]);

                switch (((Button)sender).Name)
                {
                    case "bt_UP":
                        if (index > 0)
                        {
                            Log.AddManualLog("更改站別", "上移" + item + "站別順序", Convert.ToString(index + 1), index.ToString());
                            string item2 = listBox1.Items[index - 1].ToString();
                            int Group2 = Convert.ToInt16(Produce.Station.Group[item2]);
                            listBox1.Items[index - 1] = item;
                            listBox1.Items[index] = item2;

                            Produce.SetGroup(item, Group2);
                            Produce.SetGroup(item2, Group);

                            listBox1.Refresh();
                            string newstations = "";
                            for (int i = 0; i < listBox1.Items.Count; i++)
                            {
                                newstations += listBox1.Items[i].ToString() + ",";
                            }

                            newstations = newstations.Substring(0, newstations.Length - 1);
                            Produce.SetStationName(newstations);

                            ChangeStation();

                            listBox1.SelectedIndex = index - 1;
                        }
                        break;

                    case "bt_Dowm":
                        if (index < listBox1.Items.Count - 1)
                        {
                            Log.AddManualLog("更改站別", "下移" + item + "站別順序", Convert.ToString(index + 1), Convert.ToString(index + 2));
                            string item2 = listBox1.Items[index + 1].ToString();
                            int Group2 = Convert.ToInt16(Produce.Station.Group[item2]);
                            listBox1.Items[index + 1] = item;
                            listBox1.Items[index] = item2;

                            Produce.SetGroup(item, Group2);
                            Produce.SetGroup(item2, Group);

                            listBox1.Refresh();
                            string newstations = "";
                            for (int i = 0; i < listBox1.Items.Count; i++)
                            {
                                newstations += listBox1.Items[i].ToString() + ",";
                            }

                            newstations = newstations.Substring(0, newstations.Length - 1);
                            Produce.SetStationName(newstations);
                            ChangeStation();

                            listBox1.SelectedIndex = index + 1;
                        }
                        break;
                }
            }
        }

        private void ChangeStation()
        {
            Point posion = allatsui1.Location;
            Size size = allatsui1.Size;
            Font font = allatsui1.Font;
            Color pagecolor = allatsui1.PageBackColor;
            allatsui1.Dispose();
            allatsui1 = null;

            Produce.yulans.Controls.Clear();
            panel_yulan.Controls.Clear();

            tabPage1.Controls.Remove(allatsui1);

            autoPanel5.Refresh();

            GroupArray.Clear();


            allatsui1 = new ALLATSUI();
            allatsui1.Size = size;
            allatsui1.Location = posion;
            allatsui1.Font = font;
            allatsui1.PageBackColor = pagecolor;
            tabPage1.Controls.Add(allatsui1);

            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                int Group = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[p].ToString()]);
                if (!GroupArray.Contains(Group))
                {
                    GroupArray.Add(Group);
                }

                if (GetGroupIndex(Produce.Station.NameAll[p].ToString()) == 0)
                {
                    Produce.SetWaitTestBuffer(Produce.Station.NameAll[p].ToString(), 0);
                }
            }

            InitialUI();
            InitialYuLan();
        }

        private void bt_ChangeName_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }



            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }



            int index = listBox1.SelectedIndex;
            string newstations = "";
            string oldname = listBox1.Items[index].ToString();
            string name = tbox_stationname.Text.Trim();

            Log.AddManualLog("更改站別", "更改站別名稱", oldname, name);

            int scount = ((int[])Produce.Station.NumberList[oldname]).Length;
            int timeout = Convert.ToInt32(Produce.Station.TimeOut[oldname]);

            listBox1.Items[index] = name;

            for (int i = 0; i < listBox1.Items.Count; i++)
            {
                newstations += listBox1.Items[i].ToString() + ",";
            }

            newstations = newstations.Substring(0, newstations.Length - 1);

            Produce.SetStationName(newstations);
            Produce.SetStationCount(name, scount);
            Produce.SetStationTimeout(name, timeout);
            Produce.SetGroup(name, Convert.ToInt16(Produce.Station.Group[oldname]));

            ChangeStation();

            listBox1.SelectedIndex = -1;
            listBox1.SelectedIndex = index;


        }

        private void bt_AddFix_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int index = listBox1.SelectedIndex;
            string stationname = listBox1.SelectedItem.ToString();
            int count = ((int[])Produce.Station.NumberList[stationname]).Length;
            Produce.SetStationCount(stationname, count + 1);
            ChangeStation();

            listBox1.SelectedIndex = -1;
            listBox1.SelectedIndex = index;
        }

        private void bt_DeleteFix_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int index = listBox1.SelectedIndex;
            string stationname = listBox1.SelectedItem.ToString();
            int count = ((int[])Produce.Station.NumberList[stationname]).Length;

            if (count > 1)
            {
                Produce.SetStationCount(stationname, count - 1);

                ChangeStation();

                listBox1.SelectedIndex = -1;
                listBox1.SelectedIndex = index;

            }
        }

        private void bt_changrtime_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            try
            {
                int time = Convert.ToInt32(tBox_timeout.Text);
                int index = listBox1.SelectedIndex;
                string stationname = listBox1.SelectedItem.ToString();
                int[] List = ((int[])Produce.Station.NumberList[stationname]);

                Produce.SetStationTimeout(stationname, time);

                for (int i = 0; i < List.Length; i++)
                {
                    allatsui1.ATS[List[i] - 1].TimeOut = time;
                }

            }
            catch (Exception ex)
            {

            }


        }
        private void DetectException()
        {
            while (true)
            {

                if (Produce.MainWarning != "")
                {
                    AddWarning(Produce.MainWarning);
                }

                if (Produce.RobotWarning != "")
                {
                    bRobotwarned = true;
                    AddWarning(Produce.RobotWarning);

                }
                else
                {
                    if (bRobotwarned)
                    {
                        bRobotwarned = false;
                        QuxiaoWarning();
                    }
                }

                if (!Produce.bNotUseSafeDoor && bSafeDoor)
                {
                    if (!bDoorOpend)
                    {
                        bDoorOpend = true;

                        if (bRobotconnected)
                        {
                            bRobotPaused = true;
                            Produce.Epson.SendSystemMsg_Only_Epson("$Pause,0");
                        }

                        ClickButton(bt_Pause);
                    }

                    AddWarning("安全門被打開,系統暫停");
                }
                else
                {
                    bDoorOpend = false;


                    if (sWarning == "安全門被打開")
                    {
                        if (fisrt_run)
                        {
                            Produce.Epson.SendSystemMsg_Only_Epson("$Pause,0");
                            AddWarning("手臂停止");
                            AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.OK, "請確認人員已經離開手臂運行區域后點擊開始按鈕\r\nPlease stand far away robot");
                            _warnForm.ShowDialog();
                        }
                        else
                            fisrt_run = true;
                        QuxiaoWarning();
                       
                    }









                    //if (sWarning == "安全門被打開")
                    //{
                    //    QuxiaoWarning();
                    //    SetLabelTextCallback(lb_WarnMSG, "系統已暫停", Color.Yellow);
                    //}
                }


                if (bNGFull)
                {
                    //if (!bNGFullWarned)
                    //{
                    //    bNGFullWarned = true;         
                    //}

                    AddWarning("NG區已滿,請清空");
                }
                else
                {
                    if (sWarning == "NG區已滿,請清空")
                    {
                        QuxiaoWarning();
                    }
                }


                Thread.Sleep(100);

            }
        }

        public void RunTime()
        {
            beginTime = DateTime.Now;

            TimeSpan pcruntime;
            TimeSpan midTime;
            double Hours = 0;
            double UPH_Total = 0;
            double UPH_Pass = 0;
            double Minutes = 0;
            int t = 0;
            lasttotaldut = Produce.TotalDUTCount;
            lastpassdut = Produce.PassDUTCount;
            while (true)
            {
                midTime = DateTime.Now - beginTime;
                SetLabelTextCallback(this.label_RunTime, midTime.Days + "天 " + midTime.Hours + "時 " + midTime.Minutes + "分 " + midTime.Seconds + "秒", Color.DarkSlateGray);
                pcruntime = AutoMationTest.Common.SysInfo.GetSystemUpTime();
                SetLabelTextCallback(label_PCOpenTime, pcruntime.Days + "天 " + pcruntime.Hours + "時 " + pcruntime.Minutes + "分 " + pcruntime.Seconds + "秒", Color.DarkSlateGray);
                SetLabelTextCallback(label_Total, Produce.TotalDUTCount.ToString(), Color.DarkSlateGray);
                SetLabelTextCallback(label_Pass, Produce.PassDUTCount.ToString(), Color.DarkSlateGray);

                int setday = Convert.ToInt16(Produce.pcruntimeset[0]);
                int sethour = Convert.ToInt16(Produce.pcruntimeset[1]);

                if ((pcruntime.Days * 24 + pcruntime.Hours) >= (setday * 24 + sethour))
                {
                    if (!pctimeover)
                    {
                        pctimeover = true;
                        Log.AddMainLog("電腦運行時間超過設定時間");

                    }
                }
                else
                {
                    pctimeover = false;
                }

                if (t == 180)
                {
                    t = 0;
                    //if (bRun)
                    //{
                    Minutes += 3;
                    Hours = Math.Round(Minutes / 60, 2);
                    UPH_Total = Math.Round((Produce.TotalDUTCount - lasttotaldut) / Hours, 2);
                    UPH_Pass = Math.Round((Produce.PassDUTCount - lastpassdut) / Hours, 2);

                    //SetLabelTextCallback(this.label_Exception, Hours.ToString(), Color.DarkSlateGray);
                    SetLabelTextCallback(this.label_UPH_Total, UPH_Total.ToString(), Color.DarkSlateGray);
                    SetLabelTextCallback(this.label_UPH_Pass, UPH_Pass.ToString(), Color.DarkSlateGray);
                    //}
                    //bRun = false;
                }
                Thread.Sleep(1000);
                t++;
            }
        }

        delegate void dSetLabelTextCallback(Label label, string msg, Color color);
        public void SetLabelTextCallback(Label label, string msg, Color color)
        {
            if (label.InvokeRequired)
            {
                dSetLabelTextCallback d = new dSetLabelTextCallback(SetLabelTextCallback);
                label.Invoke(d, new object[] { label, msg, color });
            }
            else
            {
                label.Text = msg;
                if (label.ForeColor != color)
                {
                    label.ForeColor = color;
                }
                //tb.ScrollToCaret();// 捲動到最後一個插入位置
            }
        }

        delegate void dSetTextBoxCallback(TextBox tbox, string msg);
        public void SetTextBoxCallback(TextBox tbox, string msg)
        {
            if (tbox.InvokeRequired)
            {
                dSetTextBoxCallback d = new dSetTextBoxCallback(SetTextBoxCallback);
                tbox.Invoke(d, new object[] { tbox, msg });
            }
            else
            {
                tbox.Text = msg;
            }
        }

        delegate void dSetPicbox(PictureBox pb, Image img);
        public void SetPicbox(PictureBox pb, Image img)
        {
            if (pb.InvokeRequired)
            {
                dSetPicbox d = new dSetPicbox(SetPicbox);
                pb.Invoke(d, new object[] { pb, img });
            }
            else
            {
                pb.Image = img;
            }
        }

        delegate void dSetButtonPic(Button pb, Image img);
        public void SetButtonPic(Button pb, Image img)
        {
            if (pb.InvokeRequired)
            {
                dSetButtonPic d = new dSetButtonPic(SetButtonPic);
                pb.Invoke(d, new object[] { pb, img });
            }
            else
            {
                pb.BackgroundImage = img;
            }
        }

        delegate void dClickButton(Button bt);
        public void ClickButton(Button bt)
        {
            if (bt.InvokeRequired)
            {
                dClickButton d = new dClickButton(ClickButton);
                bt.Invoke(d, new object[] { bt });
            }
            else
            {
                bt.PerformClick();
                //pb.Refresh();
            }
        }

        delegate void dSetcombox(ComboBox lb);
        public void Clearcombox(ComboBox lb)
        {
            if (lb.InvokeRequired)
            {
                dSetcombox d = new dSetcombox(Clearcombox);
                lb.Invoke(d, new object[] { lb });
            }
            else
            {
                lb.Items.Clear();
            }
        }
        delegate void dSetcombox1(ComboBox lb, string item);
        public void Addcombox(ComboBox lb, string item)
        {
            if (lb.InvokeRequired)
            {
                dSetcombox1 d = new dSetcombox1(Addcombox);
                lb.Invoke(d, new object[] { lb, item });
            }
            else
            {
                lb.Items.Add(item);
            }
        }

        delegate void dSetcombox2(ComboBox lb, int index);
        public void Slectcombox(ComboBox lb, int index)
        {
            if (lb.InvokeRequired)
            {
                dSetcombox2 d = new dSetcombox2(Slectcombox);
                lb.Invoke(d, new object[] { lb, index });
            }
            else
            {
                lb.SelectedIndex = index;
            }
        }

        delegate void dSetUserSW(UserSwitch usw, bool bon);
        public void SetUserSW(UserSwitch usw, bool bon)
        {
            if (usw.InvokeRequired)
            {
                dSetUserSW d = new dSetUserSW(SetUserSW);
                usw.Invoke(d, new object[] { usw, bon });
            }
            else
            {
                if (usw.SwitchStatus != bon)
                    usw.SwitchStatus = bon;
            }
        }

        delegate void dSetRichBox(RichTextBox rbox);
        public void ClearRichBox(RichTextBox rbox)
        {
            if (rbox.InvokeRequired)
            {
                dSetRichBox d = new dSetRichBox(ClearRichBox);
                rbox.Invoke(d, new object[] { rbox });
            }
            else
            {

                rbox.Clear();
            }
        }

        public void ScrollRichBox(RichTextBox rbox)
        {
            if (rbox.InvokeRequired)
            {
                dSetRichBox d = new dSetRichBox(ScrollRichBox);
                rbox.Invoke(d, new object[] { rbox });
            }
            else
            {

                rbox.ScrollToCaret();
            }
        }

        delegate void dSetRichBoxText(RichTextBox rbox, string text);
        public void SelectRichBoxText(RichTextBox rbox, string text)
        {
            if (rbox.InvokeRequired)
            {
                dSetRichBoxText d = new dSetRichBoxText(SelectRichBoxText);
                rbox.Invoke(d, new object[] { rbox, text });
            }
            else
            {

                rbox.SelectedText = text;
            }
        }

        delegate void dSetRichBoxColor(RichTextBox rbox, Color color);
        public void SetRichBoxTextColor(RichTextBox rbox, Color color)
        {
            if (rbox.InvokeRequired)
            {
                dSetRichBoxColor d = new dSetRichBoxColor(SetRichBoxTextColor);
                rbox.Invoke(d, new object[] { rbox, color });
            }
            else
            {

                rbox.SelectionBackColor = color; ;
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


        delegate void dSetOVLED(OvalShape ovalShape, bool bon);
        public void SetOVLED(OvalShape ovalShape, bool bon)
        {
            if (ovalShape.FindForm().InvokeRequired)
            {
                dSetOVLED d = new dSetOVLED(SetOVLED);
                ovalShape.FindForm().Invoke(d, new object[] { ovalShape, bon });
            }
            else
            {
                Color col;

                if (bon)
                {
                    col = Color.Lime;
                }
                else
                {
                    col = Color.Red;
                }

                if (ovalShape.FillColor != col)
                {
                    ovalShape.FillColor = col;
                    ovalShape.Refresh();
                    ovalShape.Refresh();
                }
            }
        }

        private string Descartes(List<string[]> list, int count, List<string> result, string data)
        {
            string temp = data;
            //获取当前数组
            string[] astr = list[count];
            //循环当前数组
            foreach (var item in astr)
            {

                if (count + 1 < list.Count)
                {
                    temp += Descartes(list, count + 1, result, data + item);
                }
                else
                {
                    result.Add(data + item);
                }

            }

            return temp;
        }

        private ArrayList Descartes(List<int[]> list, int count)
        {
            ArrayList temp = new ArrayList();
            //获取当前数组
            int[] astr = list[count];
            //循环当前数组
            for (int i = 0; i < astr.Length; i++)
            {
                if (count < list.Count - 1)
                {
                    temp = Descartes(list, count + 1);//, result, item);

                    //if (Produce.QUEUE.Exist(astr[i].ToString()))
                    //{
                    //    if (Produce.QUEUE.Exist(astr[i], Produce.RobotCMD.PASS))
                    //    {
                    //        temp.Add(astr[i]);
                    //    }
                    //    else
                    //    {
                    //        temp.Add(astr[i]);
                    //        break;
                    //    }
                    //}
                    //else
                    //{
                    //    temp.Clear();
                    //}
                }
                else
                {
                    if (Produce.QUEUE.Exist(astr[i].ToString()))
                    {
                        if (Produce.QUEUE.Exist(astr[i], Produce.RobotCMD.PASS))
                        {
                            temp.Add(astr[i]);
                        }
                        else
                        {
                            temp.Add(astr[i]);
                            break;
                        }
                    }
                    else
                    {
                        temp.Clear();
                        continue;
                    }
                }

            }

            return temp;
        }

        private bool CheckGoldenSample(ArrayList StationArray, ref ArrayList GoldentestList)
        {

            bGoldenYouLiao = GetGoldenLiao();

            if (!bGoldenYouLiao || !StationArray.Contains(GoldenSampleStaion))//|| bRobotGetLiao)
            {
                if (!bGoldenYouLiao)
                {
                    int[] fixListg = (int[])Produce.Station.NumberList[GoldenSampleStaion];
                    for (int b = 0; b < fixListg.Length; b++)
                    {
                        if (allatsui1.ATS[fixListg[b] - 1].bGoldenSample && !allatsui1.ATS[fixListg[b] - 1].bAlreadyTestGolden)
                        {
                            Produce.MainWarning = "請投放標準件";
                            break;
                        }
                    }
                }

                return false;
            }

            if (bGoldenYouLiao && Produce.MainWarning == "請投放標準件")
            {
                QuxiaoWarning();
            }

            int goldenindex = -1;
            bool bCanNotTest = true;
            bool bGoldentestReady = false;
            GoldentestList = new ArrayList();
            goldenindex = StationArray.IndexOf(GoldenSampleStaion);
            ArrayList allist = new ArrayList();
            ArrayList allist1 = new ArrayList();

            allist.Add(GoldenSampleStaion);

            for (int w = goldenindex; w < StationArray.Count; w++)
            {
                allist1.Add(StationArray[w].ToString());
            }

            //ArrayList[] alstation = new ArrayList[StationArray.Count];
            //ArrayList[] alpriority = new ArrayList[StationArray.Count];

            //for (int m = 0; m < allist.Count; m++)
            //{
            ArrayList alstation = new ArrayList();
            ArrayList alpriority = new ArrayList();

            int[] fixList = (int[])Produce.Station.NumberList[allist[0].ToString()];

            bool bExistSignal = false;

            //根據隊列中信號的先後順序加入，更準確
            for (int m1 = 0; m1 < Produce.QUEUE.GetQueueLength(); m1++)
            {
                int snum = Convert.ToInt32(Produce.QUEUE[m1].StationNumber);
                if (fixList.Contains(snum) && allatsui1.ATS[snum - 1].bGoldenSample && !allatsui1.ATS[snum - 1].bAlreadyTestGolden)
                {
                    bExistSignal = true;
                    int Priority = Convert.ToInt32(Produce.Station.FixturePriority[snum]);
                    alstation.Add(snum);
                    alpriority.Add(Priority);
                }
            }



            if (!bExistSignal)
            {

                bCanNotTest = true;

            }
            else
            {
                int[] SortList = SortFunc.SortArrayGulu(alstation, alpriority);// SortFunc.SortGuluGuluHash(ht[m]);

                ArrayList nextstationlist = new ArrayList();
                ArrayList nexttestlist = new ArrayList();

                for (int k = 1; k < allist1.Count; k++)
                {
                    nextstationlist.Add(allist1[k].ToString());
                }
                if (nextstationlist.Count > 0)
                {
                    for (int i = 0; i < SortList.Length; i++)
                    {
                        if (Produce.QUEUE.Exist(SortList[i], Produce.RobotCMD.PASS))
                        {
                            if (JiaoHu(nextstationlist, ref  nexttestlist, 0))
                            {
                                bGoldentestReady = true;
                                GoldentestList.Add(SortList[i]);
                                for (int h = 0; h < nexttestlist.Count; h++)
                                {
                                    GoldentestList.Add(nexttestlist[h]);
                                }
                                break;
                            }
                            else
                            {
                                if (PutWaitTestBuffer(allist1, ref nexttestlist, true))
                                {
                                    bGoldentestReady = true;

                                    for (int h = 0; h < nexttestlist.Count; h++)
                                    {
                                        GoldentestList.Add(nexttestlist[h]);
                                    }
                                    break;
                                }

                            }
                        }
                        else
                        {
                            GoldentestList.Add(SortList[i]);
                            bGoldentestReady = true;
                            break;
                        }
                    }
                }
                else
                {
                    GoldentestList.Add(SortList[0]);
                    bGoldentestReady = true;
                }

                if (bGoldentestReady)
                {
                    bCanNotTest = false;

                }
            }

            if (!bGoldentestReady)
            {
                bCanNotTest = true;
            }

            //if (bCanNotTest)
            //{
            //    break;
            //}
            //}

            return !bCanNotTest;
        }

        private int PutRetestBuffer(int FixNum, string StationName)
        {
            int Bufferid = 0;

            int rebuffrcount = Convert.ToInt32(Produce.Station.ReTestBuffer[StationName]);
            int fixnum = -1;
            string bsn = "";
            //bool bReBufferEmpty = false;
            for (int d = 0; d < rebuffrcount; d++)
            {
                Produce.GetReTestInfo(StationName, d + 1, ref fixnum, ref bsn);

                if (fixnum == 0)//Retest Buffer為空,可以做
                {
                    //bReBufferEmpty = true;
                    Bufferid = d + 1;
                    break;
                }

            }

            return Bufferid;
        }

        private bool JiaoHu(ArrayList StationArray, ref ArrayList testlist, int NGFixnum)
        {
            bool bCanNotTest = true;
            bool bPassNoNext = false;
            bool bRetestNextPass = false;
            testlist = new ArrayList();

            #region 站別的交互

            ArrayList[] alstation = new ArrayList[StationArray.Count];
            ArrayList[] alpriority = new ArrayList[StationArray.Count];

            int index = 0;
            for (int m = 0; m < StationArray.Count; m++)
            {

                alstation[m] = new ArrayList();
                alpriority[m] = new ArrayList();

                int[] fixList = (int[])Produce.Station.NumberList[StationArray[m].ToString()];
                bool bExistSignal = false;

                #region 根據隊列中信號看是否有當站信號
                //根據隊列中信號的先後順序加入，更準確
                for (int m1 = 0; m1 < Produce.QUEUE.GetQueueLength(); m1++)
                {
                    int snum = Convert.ToInt32(Produce.QUEUE[m1].StationNumber);
                    if (fixList.Contains(snum))
                    {

                        if (m == 0 & NGFixnum == snum)
                        {

                        }
                        else
                        {
                            if (!bGoldentest)
                            {
                                if (allatsui1.ATS[snum - 1].bGoldenSample && !allatsui1.ATS[snum - 1].bAlreadyTestGolden)
                                {
                                    continue;
                                }
                            }

                            if (bQingLiao)
                            {
                                Produce.RobotCMD cmd = (Produce.RobotCMD)Produce.QUEUE[m1].robotCmd;
                                if (cmd == Produce.RobotCMD.Put)
                                {
                                    continue;
                                }
                            }


                            bExistSignal = true;
                            int Priority = Convert.ToInt32(Produce.Station.FixturePriority[snum]);
                            alstation[m].Add(snum);
                            alpriority[m].Add(Priority);
                        }
                    }
                }
                #endregion

                if (!bExistSignal)
                {
                    #region 下一站無信號看上一站
                    if (m > 0)
                    {
                        //非首站發現無信號，看上一站的其他治具
                        m = m - 2;//m-2是因為下一個循環m又會自動+1，綜合後就變為m-1
                        index = 1;
                        testlist.RemoveAt(testlist.Count - 1);
                        //testlist.RemoveAt(testlist.Count - 1);
                    }
                    #endregion

                    #region 首站無信號，無法測試
                    else
                    {
                        //首站不存在信號無法繼續測試；
                        bCanNotTest = true;
                        break;
                    }
                    #endregion
                }
                else
                {
                    int[] SortList = SortFunc.SortArrayGulu(alstation[m], alpriority[m]);// SortFunc.SortGuluGuluHash(ht[m]);



                    #region 下一站有信號
                    if (index == 0)
                    {
                        #region Pass信號
                        //沒有遇到下一站不存在信號
                        if (Produce.QUEUE.Exist(SortList[index], Produce.RobotCMD.PASS))
                        {
                            //Pass就一直疊加
                            testlist.Add(SortList[0]);
                            //最後一站就出來
                            if (m == StationArray.Count - 1)
                            {
                                bCanNotTest = false;
                                break;
                            }
                            //如果是剛測完標準件，標準件就是最後出口,不用再看下一站信號了
                            if (allatsui1.ATS[SortList[0] - 1].bGoldenSample && allatsui1.ATS[SortList[0] - 1].bAlreadyTestGolden)
                            {
                                bCanNotTest = false;
                                break;
                            }
                        }
                        #endregion

                        #region Retest 信號放Buffer
                        else if (Produce.QUEUE.Exist(SortList[index], Produce.RobotCMD.Retest))
                        {
                            //Retest信號看Retest Buffer

                            int bufferid = PutRetestBuffer(SortList[index], StationArray[m].ToString());
                            if (bufferid != 0)//buffer有空的,可以放料了
                            {
                                bCanNotTest = false;
                                testlist.Add(SortList[0]);
                                testlist.Add("ReTestBuffer_" + StationArray[m].ToString() + "_" + bufferid.ToString());
                                break;
                            }
                            else
                            {
                                #region Buffer區滿了,看別的非retest信號
                                bool bExistOther = false;
                                bool bExistNotPass = false;
                                for (int k = index; k < SortList.Length; k++)
                                {
                                    if (!Produce.QUEUE.Exist(SortList[k], Produce.RobotCMD.Retest))
                                    {
                                        bExistOther = true;
                                        testlist.Add(SortList[k]);
                                        if (!Produce.QUEUE.Exist(SortList[k], Produce.RobotCMD.PASS))
                                        {
                                            bExistNotPass = true;
                                        }
                                        break;
                                    }
                                }

                                if (bExistOther)
                                {
                                    if (bExistNotPass)
                                    {
                                        bCanNotTest = false;
                                        break;
                                    }
                                    else
                                    {
                                        bRetestNextPass = true;

                                        #region Pass信號
                                        //沒有遇到下一站不存在信號

                                        //Pass就一直疊加

                                        //最後一站就出來
                                        if (m == StationArray.Count - 1)
                                        {
                                            bCanNotTest = false;
                                            break;
                                        }
                                        //如果是剛測完標準件，標準件就是最後出口,不用再看下一站信號了
                                        if (allatsui1.ATS[SortList[0] - 1].bGoldenSample && allatsui1.ATS[SortList[0] - 1].bAlreadyTestGolden)
                                        {
                                            bCanNotTest = false;
                                            break;
                                        }

                                        #endregion
                                    }
                                }
                                else
                                {
                                    //本站全都是retest信號，Buffer又滿了，沒法做
                                    bCanNotTest = true;
                                    break;
                                }

                                #endregion
                            }

                        }
                        #endregion

                        #region 非PASS/非Retest信號
                        else
                        {//優先級最高的為非PASS信號，可以直接做了
                            bCanNotTest = false;
                            testlist.Add(SortList[0]);
                            break;
                        }
                        #endregion
                    }
                    #endregion

                    #region 下一站無信號
                    else
                    {
                        //發現下一站無信號了，直接看本站第一個非PASS信號，PASS的都不用看了
                        bool bExistOther = false;
                        for (int k = index; k < SortList.Length; k++)
                        {
                            if (!Produce.QUEUE.Exist(SortList[k], Produce.RobotCMD.PASS))
                            {
                                if (Produce.QUEUE.Exist(SortList[k], Produce.RobotCMD.Retest))
                                {
                                    int bufferid = PutRetestBuffer(SortList[index], StationArray[m].ToString());
                                    if (bufferid != 0)//buffer有空的,可以放料了
                                    {
                                        bExistOther = true;
                                        bCanNotTest = false;
                                        testlist.Add(SortList[k]);
                                        testlist.Add("RetestBuffer_" + StationArray[m].ToString() + "_" + bufferid.ToString());
                                        break;
                                    }
                                    else
                                    {
                                        continue;
                                    }
                                }
                                else
                                {
                                    //非PASS信號中優先級最高的，可以直接做了
                                    //如果是之前是上一站retest,本站pass,下一站沒信號,把本站原先加入的pass先刪掉
                                    if (bRetestNextPass)
                                    {
                                        testlist.RemoveAt(testlist.Count - 1);
                                    }


                                    bExistOther = true;
                                    testlist.Add(SortList[k]);
                                    break;
                                }
                            }
                        }

                        if (bExistOther)
                        {

                            bCanNotTest = false;
                            break;
                        }
                        else
                        {
                            //下一站無信號，但本站全部又是PASS信號，只能再看上一站有沒有非PASS信號
                            if (m > 0)
                            {

                                m = m - 2;
                                index = 1;
                                //如果是第一次發現全PASS，不用清testlist，因為發現下一站無信號時已經清掉了。
                                if (bPassNoNext)
                                {
                                    testlist.RemoveAt(testlist.Count - 1);
                                }

                                bPassNoNext = true;

                            }
                            else
                            {
                                bCanNotTest = true;
                                break;
                            }
                        }
                    }
                    #endregion
                }

            }
            #endregion

            return !bCanNotTest;

        }


        private bool PickBuffer(ArrayList StationArray, ref ArrayList testlist, string Buffername)
        {
            bool bCanNotTest = true;
            testlist = new ArrayList();
            int startindex = 0;
            int NGFixNum = 0;
            if (Buffername == "WaitTestBuffer")
            {
                startindex = 1;
                NGFixNum = 0;
            }
            else
            {
                startindex = 0;
            }


            for (int m = startindex; m < StationArray.Count; m++)//首站無待測buffer
            {
                int wbufferFix = 0;
                string wbufferSN = "NONE";
                string StationName = StationArray[m].ToString();
                int BuffCount = 0;
                if (Buffername == "WaitTestBuffer")
                {
                    BuffCount = Convert.ToInt32(Produce.Station.WaitTestBuffer[StationName]);
                }
                else
                {
                    BuffCount = Convert.ToInt32(Produce.Station.ReTestBuffer[StationName]);
                }
                if (BuffCount == 0)
                {
                    if (m != StationArray.Count - 1)
                    {
                        continue;
                    }
                    else
                    {
                        bCanNotTest = true;
                    }
                }
                else
                {
                    bool bBufferYouLiao = false;
                    int bBufferID = 0;
                    for (int b = 0; b < BuffCount; b++)
                    {
                        if (Buffername == "WaitTestBuffer")
                        {
                            Produce.GetWaitTestInfo(StationName, b + 1, ref wbufferFix, ref wbufferSN);
                        }
                        else
                        {
                            Produce.GetReTestInfo(StationName, b + 1, ref wbufferFix, ref wbufferSN);
                        }
                        if (wbufferFix != 0)
                        {
                            bBufferID = b + 1;
                            if (Buffername != "WaitTestBuffer")
                            {
                                NGFixNum = wbufferFix;
                            }
                            bBufferYouLiao = true;
                            break;
                        }
                    }

                    if (bBufferYouLiao)
                    {
                        ArrayList nextstations = new ArrayList();

                        for (int k = m; k < StationArray.Count; k++)
                        {
                            nextstations.Add(StationArray[k].ToString());
                        }


                        if (JiaoHu(nextstations, ref testlist, NGFixNum))
                        {

                            testlist.Insert(0, Buffername + "_" + StationName + "_" + bBufferID);

                            bCanNotTest = false;
                            break;
                        }
                        else
                        {
                            if (m != StationArray.Count - 1)
                            {
                                continue;
                            }
                            else
                            {
                                bCanNotTest = true;
                            }
                        }

                    }
                    else
                    {
                        if (m != StationArray.Count - 1)
                        {
                            continue;
                        }
                        else
                        {
                            bCanNotTest = true;
                        }
                    }
                }
            }


            return !bCanNotTest;
        }

        private bool PutWaitTestBuffer(ArrayList StationArray, ref ArrayList testlist, bool bgolden)
        {
            bool bCanNotTest = true;
            int touliaonum = 0;
            //bYouLiao = GetTouLiao(DoingGroup, ref touliaonum);

            if (!bRobotGetLiao && !bGoldenYouLiao)//(!bYouLiao || !bGoldenYouLiao)
            {
                return false;
            }

            testlist = new ArrayList();
            for (int m = 0; m < StationArray.Count - 1; m++)//首站無待測buffer,要有下一站
            {
                int wbufferFix = 0;
                string wbufferSN = "NONE";
                string StationNameOver = StationArray[m].ToString();
                string StationName = StationArray[m + 1].ToString();
                int BuffCount = Convert.ToInt32(Produce.Station.WaitTestBuffer[StationName]);
                if (BuffCount == 0)
                {
                    if (m != StationArray.Count - 1)
                    {
                        continue;
                    }
                    else
                    {
                        bCanNotTest = true;
                    }
                }
                else
                {
                    bool bBufferYouLiao = true;
                    int bBufferID = 0;
                    for (int b = 0; b < BuffCount; b++)
                    {
                        Produce.GetWaitTestInfo(StationName, b + 1, ref wbufferFix, ref wbufferSN);

                        if (wbufferFix == 0)
                        {
                            bBufferID = b + 1;
                            bBufferYouLiao = false;
                            break;
                        }
                    }

                    if (!bBufferYouLiao)
                    {

                        ArrayList allist = new ArrayList();

                        for (int p = 0; p < m + 1; p++)
                        {
                            allist.Add(StationArray[p].ToString());
                        }

                        if (JiaoHu(allist, ref testlist, 0))
                        {
                            bCanNotTest = false;
                            if (!bgolden)
                            {
                                testlist.Insert(0, "投料點_Group" + DoingGroup.ToString() + "_" + touliaonum.ToString());
                            }
                            testlist.Add("WaitTestBuffer_" + StationName + "_" + bBufferID.ToString());
                            break;
                        }
                        else
                        {
                            if (m != StationArray.Count - 1)
                            {
                                continue;
                            }
                            else
                            {
                                bCanNotTest = true;
                            }
                        }

                    }
                    else
                    {
                        if (m != StationArray.Count - 1)
                        {
                            continue;
                        }
                        else
                        {
                            bCanNotTest = true;
                        }
                    }
                }
            }

            return !bCanNotTest;
        }

        private bool BufferTest(ArrayList StationArray, ref ArrayList testlist)
        {
            bool bCanNotTest = true;
            testlist = new ArrayList();

            if (!PickBuffer(StationArray, ref testlist, "WaitTestBuffer"))
            {

                if (!PickBuffer(StationArray, ref testlist, "ReTestBuffer"))
                {
                    if (_testmode == TestMode.Normal)
                    {

                        if (!PutWaitTestBuffer(StationArray, ref testlist, false))
                        {
                            bCanNotTest = true;
                        }
                        else
                        {
                            bCanNotTest = false;
                        }
                    }
                    else
                    {
                        bCanNotTest = true;
                    }
                }
                else
                {
                    bCanNotTest = false;
                }

            }
            else
            {
                bCanNotTest = false;
            }

            return !bCanNotTest;
        }


        private bool CycleTest(ArrayList StationArray, ref ArrayList testlist)
        {
            bool bCanNotTest = false;
            int touliaonum = 0;

            bYouLiao = GetTouLiao(DoingGroup, ref touliaonum);

            //if (bYouLiao && !bRobotGetLiao)
            //{
            //    string LaiYuan = "投料點_g" + DoingGroup.ToString() + "_" + touliaonum.ToString();
            //    Log.AddMainLog("[Robot] 從" + LaiYuan + " 抓板");
            //    MessageBox.Show("從" + LaiYuan + " 抓產品");

            //    string tpara = "t" + touliaonum.ToString();

            //    RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser[LaiYuan + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
            //    RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick[LaiYuan + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);

            //    bRobotGetLiao = true;
            //}



            if (bYouLiao && JiaoHu(StationArray, ref testlist, 0))
            {
                testlist.Insert(0, "投料點_g" + DoingGroup.ToString() + "_" + touliaonum.ToString());

                bCanNotTest = false;
            }
            else
            {

                if (BufferTest(StationArray, ref testlist))
                {
                    bCanNotTest = false;
                }
                else
                {

                    bCanNotTest = true;

                }
            }

            return !bCanNotTest;
        }

        private bool PickGolden(ArrayList StationArray, ref ArrayList testlist)
        {
            bool bCanNotTest = true;
            testlist = new ArrayList();

            for (int i = 0; i < StationArray.Count; i++)
            {
                int[] fixList = (int[])Produce.Station.NumberList[StationArray[i].ToString()];
                bool bExistSignal = false;

                #region 根據隊列中信號看是否有當站信號
                //根據隊列中信號的先後順序加入，更準確
                for (int m1 = 0; m1 < Produce.QUEUE.GetQueueLength(); m1++)
                {
                    int snum = Convert.ToInt32(Produce.QUEUE[m1].StationNumber);
                    if (fixList.Contains(snum))
                    {
                        if (allatsui1.ATS[snum - 1].bGoldenSample && allatsui1.ATS[snum - 1].bAlreadyTestGolden)
                        {
                            testlist.Add(snum);
                            bExistSignal = true;
                            break;
                        }
                    }
                }
                #endregion

                if (!bExistSignal)
                {
                    if (i < StationArray.Count - 1)
                    {
                        continue;
                    }
                    else
                    {
                        bCanNotTest = true;
                    }
                }
                else
                {
                    bCanNotTest = false;
                    break;
                }
            }

            return !bCanNotTest;
        }

        private bool CheckGoNoGo()
        {
            while (true)
            {
                if (!bPaused && bRobotconnected)
                {
                    break;
                }
                else
                {
                    Thread.Sleep(100);
                }
            }

            return true;
        }

        private void RobotCMD(string cmd, string checkmsg, int timeout)
        {
            if (CheckGoNoGo())
            {
                string error = "";
                while (true)
                {
                    try
                    {
                        if (cmd.Split(',')[1].StartsWith("t"))
                        {
                            while (true)
                            {
                                string tnum = cmd.Split(',')[1].Replace("t", "");
                                int ioindex = Convert.ToInt32(Produce.Station.TouLiaoIO["g" + DoingGroup.ToString() + "_" + tnum]);

                                if (_myio.ReadInput(ioindex - 1) == 1)
                                {
                                    break;
                                }
                                Thread.Sleep(500);
                            }
                        }
                    }
                    catch (Exception ex)
                    {

                    }

                    if (Produce.Epson.SendCheckRobot(cmd, checkmsg, 0, true, ref error))
                    {
                        Log.AddMainLog("[Robot] 當前動作完成");
                        break;
                    }
                    else
                    {
                        AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.YesNo, Produce.RobotWarning);
                        if (DialogResult.Retry == _warnForm.ShowDialog())
                        {
                            Log.AddMainLog("[手動]選擇: 重試");
                            Produce.RobotWarning = "";
                        }
                        else
                        {
                            Log.AddMainLog("[手動]選擇: 繼續");
                            Produce.RobotWarning = "";
                            break;
                        }
                    }

                }
            }
        }

        private void RobotCMD_NoCheckGoNoGo(string cmd, string checkmsg, int timeout)
        {

            string error = "";
            while (true)
            {
                if (Produce.Epson.SendCheckRobot(cmd, checkmsg, 0, true, ref error))
                {
                    Log.AddMainLog("[Robot] 當前動作完成");
                    break;
                }
                else
                {
                    AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.YesNo, Produce.RobotWarning);
                    if (DialogResult.Retry == _warnForm.ShowDialog())
                    {
                        Log.AddMainLog("[手動]選擇: 重試");
                        Produce.RobotWarning = "";
                    }
                    else
                    {
                        Log.AddMainLog("[手動]選擇: 繼續");
                        Produce.RobotWarning = "";
                        break;
                    }
                }

            }

        }

        private void RobotTest(ArrayList _testlist, int doinggroup)
        {

            //string JiaZhua1 = "夾爪1";
            //string JiaZhua2 = "夾爪2";
            bool bpickfromRetest = false;
            int LastFixNum = 0;
            string LastSN = "NONE";

            bGoHomeAlready = false;

            #region 手臂預處理名單
            Robot.RobotDoingStation.Clear();

            for (int p1 = 0; p1 < _testlist.Count; p1++)
            {
                try
                {
                    int StationNumber = Convert.ToInt32(_testlist[p1]);
                    //int StationIndex = Convert.ToInt16(Produce.Station.Index[StationNumber]);
                    Produce.RobotDoneOver_ByStation[StationNumber - 1] = false;
                    Robot.RobotDoingStation.Add(StationNumber);
                }
                catch (Exception ex)
                {

                }
            }
            #endregion

            for (int i = 0; i < _testlist.Count; i++)
            {

                Slectcombox(comboBox5, i);

                try
                {
                    int fixnum = Convert.ToInt32(_testlist[i]);
                    string sfixnum = fixnum.ToString();

                    if (sfixnum.Length == 1)
                    {
                        sfixnum = "0" + sfixnum;
                    }
                    //int StationIndex = Convert.ToInt16(Produce.Station.Index[fixnum]);
                    string lastzone = "";
                    string lastzonepoint = "";
                    LastFixNum = fixnum;
                    LastSN = allatsui1.ATS[fixnum - 1].SN;

                    #region Check ATS Coonect
                    if (!bskiptest)
                    {
                        while (true)
                        {
                            if (allatsui1.ATS[fixnum - 1].IsConnected())
                            {
                                break;
                            }
                            else
                            {
                                Produce.MainWarning = fixnum.ToString() + "號ATS未連接";
                                Thread.Sleep(100);
                            }
                        }
                    }
                    else
                    {
                        Log.AddMainLog("跳過測試");
                    }
                    #endregion

                    #region Check Reset Count
                    if (bpickfromRetest && i == 1)
                    {
                        allatsui1.ATS[fixnum - 1].DUTTestTime = 1;
                    }
                    else
                    {
                        int retestBuffCount = Convert.ToInt32(Produce.Station.ReTestBuffer[fixnum]);
                        if (retestBuffCount > 0)
                        {
                            allatsui1.ATS[fixnum - 1].DUTTestTime = 0;
                        }
                        else
                        {
                            allatsui1.ATS[fixnum - 1].DUTTestTime = 1;
                        }
                    }
                    #endregion

                    #region Check Fix open
                    if (Produce.bControlFixture)
                    {
                        Log.AddMainLog("Check ATS[" + fixnum.ToString() + "] Fixture open?");
                        DateTime dt = DateTime.Now;
                        bool balreadyfixwarn = false;
                        while (true)
                        {
                            if (allatsui1.ATS[fixnum - 1].fix_status == TestUI.FixStatus.Open)
                            {
                                Log.AddMainLog("ATS[" + fixnum.ToString() + "] Fixture is open!");
                                break;
                            }

                            if (allatsui1.ATS[fixnum - 1].fix_status == TestUI.FixStatus.Error)
                            {
                                if (!balreadyfixwarn)
                                {
                                    balreadyfixwarn = true;
                                    Log.AddMainLog("ATS[" + fixnum.ToString() + "] Fixture Status Error!");
                                    Produce.MainWarning = fixnum.ToString() + "號治具打開異常";
                                    Log.AddExceptionLog("NONE", "治具打開異常", fixnum);
                                }
                            }
                            if (allatsui1.ATS[fixnum - 1].fix_status == TestUI.FixStatus.None)
                            {
                                if (!balreadyfixwarn)
                                {
                                    balreadyfixwarn = true;
                                    Log.AddMainLog("ATS[" + fixnum.ToString() + "] Fixture Status Error!");
                                    Produce.MainWarning = fixnum.ToString() + "號治具未連接";
                                    Log.AddExceptionLog("NONE", "治具未連接-無法確認是否打開", fixnum);
                                }
                            }

                            if (dt.AddSeconds(10) < DateTime.Now)
                            {
                                if (allatsui1.ATS[fixnum - 1].fix_status == TestUI.FixStatus.Close)
                                {
                                    if (!balreadyfixwarn)
                                    {
                                        balreadyfixwarn = true;
                                        Log.AddMainLog("ATS[" + fixnum.ToString() + "] Fixture Status Error!");
                                        Produce.MainWarning = fixnum.ToString() + "號治具未打開";
                                        Log.AddExceptionLog("NONE", "治具未打開-無法放板", fixnum);
                                    }
                                }
                            }

                            Thread.Sleep(10);
                        }
                    }
                    #endregion

                    #region Fix Pick & Put
                    if (!Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.Put))
                    {
                        Log.AddMainLog("[Robot] 從治具" + fixnum.ToString() + " 抓起測完品");
                        //MessageBox.Show(fixnum.ToString() + " 抓起測完品");

                        RobotCMD("pick," + sfixnum + "," + Produce.RobotPoint.Pick["治具_" + fixnum.ToString() + "_Pick"].ToString(), "pick_" + sfixnum + "_ok", 0);

                        #region 吸嘴耗材統計
                        if (i == 0 || (i % 2 != 0))
                        {
                            for (int h = 0; h < Produce.HaoCai.Count; h++)
                            {
                                if (Produce.HaoCai.HType[h + 1].ToString().Contains("吸嘴2吸真空"))
                                {
                                    Produce.AddHaoCai_UseCount(h + 1);
                                }
                            }
                        }
                        else
                        {
                            for (int h = 0; h < Produce.HaoCai.Count; h++)
                            {
                                if (Produce.HaoCai.HType[h + 1].ToString().Contains("吸嘴1吸真空"))
                                {
                                    Produce.AddHaoCai_UseCount(h + 1);
                                }
                            }
                        }
                        #endregion

                        if (i == 0 && _testmode == TestMode.QingLiao)
                        {

                        }
                        else
                        {
                            Log.AddMainLog("[Robot] 放下待測品到治具" + fixnum.ToString());
                            //MessageBox.Show("放下待測品到" + fixnum.ToString());
                            RobotCMD("put," + sfixnum + "," + Produce.RobotPoint.Put["治具_" + fixnum.ToString() + "_Put"].ToString(), "put_" + sfixnum + "_ok", 0);
                            RobotCMD("laser," + sfixnum + "," + Produce.RobotPoint.Laser["治具_" + fixnum.ToString() + "_Laser"].ToString(), "laser_" + sfixnum + "_ok", 0);

                        }
                    }
                    else
                    {
                        Log.AddMainLog("[Robot] 放下待測品到治具" + fixnum.ToString());
                        //MessageBox.Show("放下待測品到" + fixnum.ToString());
                        RobotCMD("put," + sfixnum + "," + Produce.RobotPoint.Put["治具_" + fixnum.ToString() + "_Put"].ToString(), "put_" + sfixnum + "_ok", 0);
                        RobotCMD("laser," + sfixnum + "," + Produce.RobotPoint.Laser["治具_" + fixnum.ToString() + "_Laser"].ToString(), "laser_" + sfixnum + "_ok", 0);

                    }

                    #region 取放板統計

                    for (int h = 0; h < Produce.HaoCai.Count; h++)
                    {
                        if (Produce.HaoCai.HType[h + 1].ToString().Contains("取放板"))
                        {
                            Produce.AddHaoCai_UseCount(h + 1);
                        }
                    }

                    #endregion

                    bRobotGetLiao = false;

                    #endregion

                    #region Check if put GoldenSample
                    if (_testlist[0].ToString().Contains("標準件") && allatsui1.ATS[fixnum - 1].bGoldenSample)
                    {
                        allatsui1.ATS[fixnum - 1].bPutGolden = true;
                    }
                    #endregion

                    #region Exit zone check
                    if (i == _testlist.Count - 1)
                    {

                        if (!bGRRTest)
                        {
                            if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.PASS))
                            {
                                lastzone = "PASS";
                            }
                            else if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.NG))
                            {
                                lastzone = "NG";
                            }
                            else if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.Put))
                            {
                                lastzone = "";
                            }
                        }
                        else
                        {
                            if (!Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.Put))
                            {
                                lastzone = "NG";
                            }

                        }
                    }
                    #endregion

                    #region delete queue & done over
                    Produce.QUEUE.Delete(_testlist[i].ToString());

                    if (!bskiptest)
                    {
                        if (i == 0 && _testmode == TestMode.QingLiao)
                        {
                            Produce.RobotDoneOver_ByStation[fixnum - 1] = false;
                            AutoMationTest.Robots.Robot.RobotDoingStation.Remove(fixnum);
                            allatsui1.ATS[fixnum - 1].status = TestUI.Status.Used;
                        }
                        else
                        {
                            Produce.RobotDoneOver_ByStation[fixnum - 1] = true;
                        }
                    }
                    else
                    {
                        Produce.RobotDoneOver_ByStation[fixnum - 1] = false;
                        AutoMationTest.Robots.Robot.RobotDoingStation.Remove(fixnum);
                        allatsui1.ATS[fixnum - 1].status = TestUI.Status.Used;
                    }
                    #endregion

                    #region qing liao ok & wait DUT
                    if (i == 0 && bQingLiao)//_testmode == TestMode.QingLiao)
                    {
                        allatsui1.ATS[fixnum - 1].status = TestUI.Status.WaitDUT;

                        allatsui1.ATS[fixnum - 1].action.StationNumber = fixnum.ToString();
                        allatsui1.ATS[fixnum - 1].action.robotCmd = Produce.RobotCMD.Put;
                        allatsui1.ATS[fixnum - 1].action.UserControlStatus = TestUI.Status.Testing;
                        allatsui1.ATS[fixnum - 1].action.ResponeServerMsg = "CtoT_placeDUTOK";
                        Produce.QUEUE.In_Check(allatsui1.ATS[fixnum - 1].action);
                    }
                    #endregion

                    if (i == _testlist.Count - 1)
                    {
                        #region Goldensample over
                        if (allatsui1.ATS[fixnum - 1].bGoldenSample && allatsui1.ATS[fixnum - 1].bAlreadyTestGolden)
                        {
                            allatsui1.ATS[fixnum - 1].bPutGolden = false;
                            if (Produce.GoldenNG_SwitchMode || lastzone == "PASS")
                            {
                                allatsui1.ATS[fixnum - 1].SetRadioButton(allatsui1.ATS[fixnum - 1].radioButton1, true);
                            }

                            if (lastzone != "")
                            {
                                Log.AddMainLog("檢查NG區是否可放料");
                                int nzonenum = 0;
                                while (true)
                                {
                                    if (GetNGZone(doinggroup, ref nzonenum))
                                    {
                                        lastzone = "n" + nzonenum.ToString();
                                        lastzonepoint = "NG區_g" + doinggroup.ToString() + "_" + nzonenum.ToString() + "_Put";
                                        break;
                                    }
                                    Thread.Sleep(50);
                                }

                                Slectcombox(comboBox5, i + 1);
                                Log.AddMainLog("[Robot] 放下標準件到NG區");//標準件區
                                //MessageBox.Show("放下標準件到NG區");
                                RobotCMD("put," + lastzone + "," + Produce.RobotPoint.Put[lastzonepoint].ToString(), "put_" + lastzone + "_ok", 0);
                            }
                        }
                        #endregion

                        #region Robot Goto Exit zone
                        else
                        {
                            if (lastzone != "")
                            {
                                if (lastzone == "PASS")
                                {

                                    Log.AddMainLog("檢查Pass區是否可放料");
                                    int pzonenum = 0;
                                    while (true)
                                    {
                                        if (GetPassZone(doinggroup, ref pzonenum))
                                        {
                                            lastzone = "p" + pzonenum.ToString();
                                            lastzonepoint = "PASS區_g" + doinggroup.ToString() + "_" + pzonenum.ToString() + "_Put";
                                            break;
                                        }

                                        Thread.Sleep(50);
                                    }

                                    #region Pass滑台統計
                                    for (int h = 0; h < Produce.HaoCai.Count; h++)
                                    {
                                        if (Produce.HaoCai.HType[h + 1].ToString().Contains("Pass滑台_" + pzonenum.ToString()))
                                        {
                                            Produce.AddHaoCai_UseCount(h + 1);
                                        }
                                    }
                                    #endregion
                                }
                                else
                                {
                                    Log.AddMainLog("檢查NG區是否可放料");
                                    int nzonenum = 0;
                                    while (true)
                                    {
                                        if (GetNGZone(doinggroup, ref nzonenum))
                                        {
                                            lastzone = "n" + nzonenum.ToString();
                                            lastzonepoint = "NG區_g" + doinggroup.ToString() + "_" + nzonenum.ToString() + "_Put";
                                            break;
                                        }

                                        Thread.Sleep(50);
                                    }

                                    #region NG滑台統計
                                    for (int h = 0; h < Produce.HaoCai.Count; h++)
                                    {
                                        if (Produce.HaoCai.HType[h + 1].ToString().Contains("NG滑台_" + nzonenum.ToString()))
                                        {
                                            Produce.AddHaoCai_UseCount(h + 1);
                                        }
                                    }
                                    #endregion
                                }


                                Slectcombox(comboBox5, i + 1);
                                Log.AddMainLog("[Robot] 放下測完品到" + lastzone);
                                //MessageBox.Show("放下測完品到" + lastzone);
                                RobotCMD("put," + lastzone + "," + Produce.RobotPoint.Put[lastzonepoint].ToString(), "put_" + lastzone + "_ok", 0);

                                #region 取放板統計

                                for (int h = 0; h < Produce.HaoCai.Count; h++)
                                {
                                    if (Produce.HaoCai.HType[h + 1].ToString().Contains("取放板"))
                                    {
                                        Produce.AddHaoCai_UseCount(h + 1);
                                    }
                                }

                                #endregion
                            }

                        }
                        #endregion
                    }


                }
                catch (Exception ex)
                {
                    if (i == 0)
                    {
                        #region Robot First Get DUT
                        string LaiYuan = _testlist[0].ToString();
                        //if (!LaiYuan.Contains("投料點"))
                        //{
                        Log.AddMainLog("[Robot] 從" + LaiYuan + " 抓板");
                        //MessageBox.Show("從" + LaiYuan + " 抓產品");
                        //}
                        if (LaiYuan.Contains("投料點"))
                        {
                            #region 投料滑台統計
                            for (int h = 0; h < Produce.HaoCai.Count; h++)
                            {
                                if (Produce.HaoCai.HType[h + 1].ToString().Contains("投料滑台_" + LaiYuan.Split('_')[LaiYuan.Split('_').Length - 1]))
                                {
                                    Produce.AddHaoCai_UseCount(h + 1);
                                }
                            }
                            #endregion

                            string tpara = "t" + LaiYuan.Split('_')[LaiYuan.Split('_').Length - 1];
                            RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser[LaiYuan + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
                            RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick[LaiYuan + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);

                        }
                        else if (LaiYuan.Contains("標準件"))
                        {
                            string tpara = "g";
                            RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser[LaiYuan + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
                            RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick[LaiYuan + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);

                        }
                        else if (LaiYuan.Contains("WaitTestBuffer"))
                        {
                            string tpara = LaiYuan.Split('_')[1] + LaiYuan.Split('_')[2];
                            RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser[LaiYuan.Split('_')[1] + "_待測Buffer_" + LaiYuan.Split('_')[2] + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
                            RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick[LaiYuan.Split('_')[1] + "_待測Buffer_" + LaiYuan.Split('_')[2] + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);

                        }
                        else if (LaiYuan.Contains("ReTestBuffer"))
                        {
                            string tpara = LaiYuan.Split('_')[1] + LaiYuan.Split('_')[2];
                            RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser[LaiYuan.Split('_')[1] + "_複測Buffer_" + LaiYuan.Split('_')[2] + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
                            RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick[LaiYuan.Split('_')[1] + "_複測Buffer_" + LaiYuan.Split('_')[2] + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);

                        }
                        #endregion

                        for (int h = 0; h < Produce.HaoCai.Count; h++)
                        {
                            if (Produce.HaoCai.HType[h + 1].ToString().Contains("吸嘴1吸真空"))
                            {
                                Produce.AddHaoCai_UseCount(h + 1);
                            }
                        }

                        #region Clear wait test buffer
                        if (LaiYuan.Contains("WaitTestBuffer"))
                        {
                            string[] ssplit = LaiYuan.Split('_');
                            Produce.SetWaitTestInfo(ssplit[1], Convert.ToInt32(ssplit[2]), 0, "NONE");
                            if (tBox_BufferStationName.Text == (ssplit[1]))
                            {
                                ((NormalBuffer)autoPanel_WaitTest.Controls[Convert.ToInt32(ssplit[2]) - 1]).FixNum = 0;
                            }
                        }
                        #endregion

                        #region Clear retest buffer
                        else if (LaiYuan.Contains("ReTestBuffer"))
                        {
                            string[] ssplit = LaiYuan.Split('_');
                            Produce.SetReTestInfo(ssplit[1], Convert.ToInt32(ssplit[2]), 0, "NONE");
                            if (tBox_BufferStationName.Text == (ssplit[1]))
                            {
                                ((NormalBuffer)autoPanel_Retest.Controls[Convert.ToInt32(ssplit[2]) - 1]).FixNum = 0;
                            }

                            bpickfromRetest = true;
                        }
                        #endregion
                    }
                    else if (i == _testlist.Count - 1)
                    {
                        #region Robot put DUT to Last Buffer
                        Log.AddMainLog("[Robot] 放板到" + _testlist[i].ToString());
                        MessageBox.Show("放板到" + _testlist[i].ToString());
                        string ChuKou = _testlist[i].ToString();
                        if (ChuKou.Contains("WaitTestBuffer"))
                        {
                            string[] ssplit = ChuKou.Split('_');
                            string tpara = ssplit[1] + ssplit[2];
                            RobotCMD("Put," + tpara + "," + Produce.RobotPoint.Put[ssplit[1] + "_待測Buffer_" + ssplit[2] + "_Put"].ToString(), "put_" + tpara + "_ok", 0);


                            Produce.SetWaitTestInfo(ssplit[1], Convert.ToInt32(ssplit[2]), LastFixNum, LastSN);
                            if (tBox_BufferStationName.Text == (ssplit[1]))
                            {
                                ((NormalBuffer)autoPanel_WaitTest.Controls[Convert.ToInt32(ssplit[2]) - 1]).FixNum = LastFixNum;
                                ((NormalBuffer)autoPanel_WaitTest.Controls[Convert.ToInt32(ssplit[2]) - 1]).SN = LastSN;
                            }
                        }
                        else if (ChuKou.Contains("ReTestBuffer"))
                        {
                            string[] ssplit = ChuKou.Split('_');
                            string tpara = ssplit[1] + ssplit[2];
                            RobotCMD("Put," + tpara + "," + Produce.RobotPoint.Put[ssplit[1] + "_複測Buffer_" + ssplit[2] + "_Put"].ToString(), "put_" + tpara + "_ok", 0);


                            Produce.SetReTestInfo(ssplit[1], Convert.ToInt32(ssplit[2]), LastFixNum, LastSN);
                            if (tBox_BufferStationName.Text == (ssplit[1]))
                            {
                                ((NormalBuffer)autoPanel_Retest.Controls[Convert.ToInt32(ssplit[2]) - 1]).FixNum = LastFixNum;
                                ((NormalBuffer)autoPanel_Retest.Controls[Convert.ToInt32(ssplit[2]) - 1]).SN = LastSN;
                            }
                        }

                        #region 取放板統計

                        for (int h = 0; h < Produce.HaoCai.Count; h++)
                        {
                            if (Produce.HaoCai.HType[h + 1].ToString().Contains("取放板"))
                            {
                                Produce.AddHaoCai_UseCount(h + 1);
                            }
                        }

                        #endregion

                        #endregion

                    }
                }

            }


        }

        private void SortByFR(string StationName)
        {
            int[] fixList = (int[])Produce.Station.NumberList[StationName];
            int nPriority = 0;
            double[] rateList = new double[fixList.Length];
            for (int i = 0; i < fixList.Length; i++)
            {
                double YR = allatsui1.ATS[fixList[i] - 1].rate;
                rateList[i] = YR;
            }

            Array.Sort(rateList, fixList);
            Array.Reverse(fixList);

            for (int j = 0; j < fixList.Length; j++)
            {
                if (j > 0)
                {
                    if (allatsui1.ATS[fixList[j] - 1].rate != allatsui1.ATS[fixList[j - 1] - 1].rate)
                    {
                        nPriority++;
                        Produce.SetFixtruePriority(fixList[j], nPriority);
                    }
                    else
                    {
                        Produce.SetFixtruePriority(fixList[j], nPriority);
                    }
                }
                else
                {
                    nPriority = 0;
                    Produce.SetFixtruePriority(fixList[j], nPriority);
                }
            }

        }

        private void showlist(ArrayList list)
        {
            string NumberList = "";

            for (int y = 0; y < list.Count; y++)
            {
                NumberList += list[y].ToString() + " --> ";
                Addcombox(comboBox5, list[y].ToString());
                try
                {
                    int fixnum = Convert.ToInt32(list[y]);
                    if (y == list.Count - 1)
                    {
                        if (allatsui1.ATS[fixnum - 1].bGoldenSample && allatsui1.ATS[fixnum - 1].bAlreadyTestGolden)
                        {
                            if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.Put))
                            {
                            }
                            else
                            {
                                NumberList += "NG區" + " --> ";//標準件區
                                Addcombox(comboBox5, "NG區");//標準件區
                            }
                        }
                        else
                        {

                            if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.PASS))
                            {
                                NumberList += "PASS區" + " --> ";
                                Addcombox(comboBox5, "PASS區");
                            }
                            else if (Produce.QUEUE.Exist(fixnum, Produce.RobotCMD.NG))
                            {
                                NumberList += "NG區" + " --> ";
                                Addcombox(comboBox5, "NG區");
                            }
                        }
                    }
                }
                catch (Exception ex)
                {

                }
            }

            NumberList = NumberList.Substring(0, NumberList.Length - 5);

            Log.AddMainLog("手臂交互順序為：" + NumberList);
        }

        private void Test()
        {
            #region Check robot is ready
            while (true)
            {
                try
                {
                    if (Robot.ReceiveMSG_From_Robot.ToLower().Contains("ready"))
                    {
                        Log.AddMainLog("robot is ready!");
                        break;
                    }
                }
                catch (Exception ex)
                {

                }
                Thread.Sleep(100);
            }
            #endregion

            #region 真空2有板放NG區

            if (_myio.ReadInput(1) == 1)
            {
                string lastzone = "";
                string lastzonepoint = "";

                Log.AddMainLog("吸嘴2有板,檢查NG區是否可放料");
                int nzonenum = 0;
                while (true)
                {
                    if (GetNGZone(0, ref nzonenum))
                    {
                        lastzone = "n" + nzonenum.ToString();
                        lastzonepoint = "NG區_g0" + "_" + nzonenum.ToString() + "_Put";
                        break;
                    }

                    Thread.Sleep(50);
                }

                Log.AddMainLog("[Robot] 放下吸嘴2未知產品到NG區");
                RobotCMD("put," + lastzone + "," + Produce.RobotPoint.Put[lastzonepoint].ToString(), "put_" + lastzone + "_ok", 0);
            }

            #endregion

            while (true)
            {
                #region PC Run time control
                if (pctimeover)
                {
                    if (!boverwarned)
                    {
                        boverwarned = true;
                        Produce.MainWarning = "電腦運行超時,請重啟電腦";
                        Log.AddRobotErrorLog("無", "PC0001");
                    }
                    Thread.Sleep(1000);
                    continue;
                }
                #endregion

                #region haocai control
                bool bhaocaiover = false;
                for (int h = 0; h < Produce.HaoCai.Count; h++)
                {
                    try
                    {
                        double dusecount = Convert.ToDouble(Produce.HaoCai.UseCount[h + 1]);
                        double dspec = Convert.ToDouble(Produce.HaoCai.Spec[h + 1]);
                        if (dusecount >= dspec)
                        {
                            bhaocaiover = true;
                            if (!bhaocaiwarned)
                            {
                                bhaocaiwarned = true;
                                Produce.MainWarning = Produce.HaoCai.Name[h + 1].ToString() + "超出使用次數,請更換";
                                Log.AddRobotErrorLog("無", "HC0001");
                            }
                            break;
                        }
                    }
                    catch (Exception exh)
                    { }
                }

                if (bhaocaiover)
                {
                    Thread.Sleep(1000);
                    continue;
                }
                #endregion

                if (!bPaused)
                {
                    bQingLiao = false;

                    #region GRR Test
                    if (bGRRTest)
                    {
                        GRRTest();
                        Thread.Sleep(500);
                        continue;
                    }
                    #endregion

                    int[] GroupList = SortFunc.SortHashTable2(Produce.Station.GroupPriority);

                    for (int i = 0; i < GroupList.Length; i++)
                    {
                        bGoldentest = false;
                        DoingGroup = GroupList[i];

                        #region 一個群組內有幾站
                        ArrayList StationArray = new ArrayList();
                        for (int j = 0; j < Produce.Station.NameAll.Length; j++)
                        {
                            string StationName = Produce.Station.NameAll[j].ToString();
                            int StationGroup = Convert.ToInt32(Produce.Station.Group[StationName]);

                            if (StationGroup == GroupList[i])
                            {
                                StationArray.Add(StationName);
                            }
                        }
                        #endregion

                        #region 根據良率確認優先級
                        if (rbton_ByFR.Checked)
                        {
                            for (int s = 0; s < StationArray.Count; s++)
                            {
                                SortByFR(StationArray[s].ToString());
                            }
                        }
                        #endregion

                        Clearcombox(comboBox5);

                        #region Golden Sample
                        if (CheckGoldenSample(StationArray, ref goldentestlist))
                        {
                            bGoldentest = true;
                            goldentestlist.Insert(0, "標準件區");

                            showlist(goldentestlist);
                            RobotTest(goldentestlist, DoingGroup);

                            break;
                        }
                        #endregion

                        if (CycleTest(StationArray, ref testlist))
                        {
                            showlist(testlist);
                            RobotTest(testlist, DoingGroup);

                            break;
                        }

                        #region 清料模式
                        if (_testmode == TestMode.QingLiao)
                        {
                            bQingLiao = true;

                            if (QingLiaoMode(StationArray, ref testlist))
                            {
                                showlist(testlist);
                                RobotTest(testlist, DoingGroup);

                                break;
                            }
                            else
                            {
                                if (!bAlreadyQingLiaoEnd)
                                {
                                    if (CheckQingLiaoEnd())
                                    {
                                        bAlreadyQingLiaoEnd = true;
                                        Produce.bNeedBaoJing = true;
                                        Produce.MainWarning = "清料模式已完成";
                                    }
                                }
                            }
                        }
                        #endregion

                        if (!bGoHomeAlready)
                        {
                            RobotCMD("gosafe,home,0,0,0,0,0,0", "gosafe_home_ok", 0);
                            //Produce.Epson.SendCheckRobot("gosafe,home,0,0,0,0,0,0", "gosafe_home_ok", 0, true, ref roborerror);
                            bGoHomeAlready = true;
                        }

                    }

                }

                Thread.Sleep(50);
            }
        }

        private bool CheckQingLiaoEnd()
        {
            bool bNotEnd = false;

            for (int i = 0; i < Produce.QUEUE.GetQueueLength(); i++)
            {
                if (Produce.QUEUE[i].robotCmd != Produce.RobotCMD.Put)
                {
                    bNotEnd = true;
                    break;
                }
            }

            if (!bNotEnd)
            {
                for (int j = 0; j < Produce.Station.Count; j++)
                {
                    if (allatsui1.ATS[j].status == TestUI.Status.Testing)
                    {
                        bNotEnd = true;
                        break;
                    }
                }
            }

            return !bNotEnd;
        }

        private bool QingLiaoMode(ArrayList StationArray, ref ArrayList testlist)
        {

            bool bCanNotTest = true;

            ArrayList _QStationList = new ArrayList();

            _QStationList = (ArrayList)StationArray.Clone();

            for (int i = 0; i < StationArray.Count; i++)
            {
                //入口必須有料，pass,ng,retest
                int[] fixList = (int[])Produce.Station.NumberList[StationArray[i].ToString()];
                bool bExistLiao = false;

                #region 根據隊列中信號看是否有當站信號

                for (int m1 = 0; m1 < Produce.QUEUE.GetQueueLength(); m1++)
                {
                    int snum = Convert.ToInt32(Produce.QUEUE[m1].StationNumber);
                    Produce.RobotCMD cmd = (Produce.RobotCMD)Produce.QUEUE[m1].robotCmd;
                    if (fixList.Contains(snum) && (cmd != Produce.RobotCMD.Put))
                    {
                        bExistLiao = true;
                        break;

                    }
                }
                #endregion

                if (bExistLiao)
                {
                    if (JiaoHu(_QStationList, ref testlist, 0))
                    {
                        bCanNotTest = false;
                    }
                    else
                    {
                        if (BufferTest(StationArray, ref testlist))
                        {
                            bCanNotTest = false;
                        }
                        else
                        {
                            bCanNotTest = true;
                        }
                    }
                }
                else
                {
                    bCanNotTest = true;
                }


                if (!bCanNotTest)
                {

                    //最後一站要改為WAIT DUT

                    break;
                }
                else
                {
                    if (i < StationArray.Count - 1)
                    {
                        _QStationList.RemoveAt(0);
                    }
                    else
                    {
                        bCanNotTest = true;
                    }
                }

            }

            return !bCanNotTest;
        }

        private void comboBox_StationName_SelectedIndexChanged(object sender, EventArgs e)
        {
            bt_ChangeSetting.Text = "更改";
            comboBox_StationNum.Items.Clear();
            comboBox_StationNum.Items.Add("所有治具");
            string SelectStationName = comboBox_StationName.Text;
            int[] List = (int[])Produce.Station.NumberList[SelectStationName];

            for (int i = 0; i < List.Length; i++)
            {
                comboBox_StationNum.Items.Add(List[i]);
            }
            comboBox_StationNum.SelectedIndex = 0;
        }

        private void bt_ChangeSetting_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (bt_ChangeSetting.Text == "更改")
            {

                if (comboBox_Freq.SelectedIndex == 2)
                {


                    string Hour = numericUpDown_Hour.Value.ToString();
                    string Minute = numericUpDown_Minute.Value.ToString();

                    string newsetting = Hour + ":" + Minute;

                    if (comboBox_StationNum.SelectedIndex != 0)
                    {
                        int StationNum = Convert.ToInt32(bt_StationNum.Text);
                        Produce.SetGoldenTime(StationNum, newsetting);
                    }
                    else
                    {
                        for (int i = 1; i < comboBox_StationNum.Items.Count; i++)
                        {
                            int StationNum = Convert.ToInt32(comboBox_StationNum.Items[i].ToString());
                            Produce.SetGoldenTime(StationNum, newsetting);
                        }
                    }
                }
                else if (comboBox_Freq.SelectedIndex == 1)
                {

                    string Hour = numericUpDown_Hour.Value.ToString();
                    string Minute = numericUpDown_Minute.Value.ToString();

                    string newsetting = Hour + ":" + Minute;

                    if (comboBox_StationNum.SelectedIndex != 0)
                    {
                        int StationNum = Convert.ToInt32(bt_StationNum.Text);
                        Produce.SetGoldenTimeOnce(StationNum, newsetting);
                    }
                    else
                    {
                        for (int i = 1; i < comboBox_StationNum.Items.Count; i++)
                        {
                            int StationNum = Convert.ToInt32(comboBox_StationNum.Items[i].ToString());
                            Produce.SetGoldenTimeOnce(StationNum, newsetting);
                        }
                    }
                }
                else
                {
                    if (comboBox_StationNum.SelectedIndex != 0)
                    {
                        int StationNum = Convert.ToInt32(bt_StationNum.Text);
                        Produce.ClearGoldenSetting(StationNum);
                    }
                    else
                    {
                        for (int i = 1; i < comboBox_StationNum.Items.Count; i++)
                        {
                            int StationNum = Convert.ToInt32(comboBox_StationNum.Items[i].ToString());
                            Produce.ClearGoldenSetting(StationNum);
                        }
                    }
                }

                bt_ChangeSetting.Text = "已變更";
            }
        }

        private void comboBox_StationNum_SelectedIndexChanged(object sender, EventArgs e)
        {
            bt_ChangeSetting.Text = "更改";

            int SelectStationNum = 0;

            if (comboBox_StationNum.SelectedIndex == 0)
            {
                SelectStationNum = Convert.ToInt32(comboBox_StationNum.Items[1]);
            }
            else
            {
                SelectStationNum = Convert.ToInt32(comboBox_StationNum.Text);
            }

            label_LastTestTime.Text = Produce.Station.GoldenLastTimeRecord[SelectStationNum].ToString();

            bt_StationNum.Text = comboBox_StationNum.Text.ToString();
            bt_StationName.Text = Produce.Station.Name[SelectStationNum].ToString();
            try
            {
                string SettingTime = Produce.Station.GoldenTestTime[SelectStationNum].ToString();

                if (SettingTime.Contains(":"))
                {

                    string sHour = SettingTime.Split(':')[0];
                    string sMinute = SettingTime.Split(':')[1];

                    int Hour = Convert.ToInt32(sHour);
                    int Minute = Convert.ToInt32(sMinute);

                    if (-1 < Hour && Hour < 24 && -1 < Minute && Minute < 60)
                    {
                        numericUpDown_Hour.Value = Hour;
                        numericUpDown_Minute.Value = Minute;
                        comboBox_Freq.SelectedIndex = 2;
                    }
                    else
                    {
                        numericUpDown_Hour.Value = 0;
                        numericUpDown_Minute.Value = 0;
                        comboBox_Freq.SelectedIndex = 0;
                    }

                }
                else
                {
                    numericUpDown_Hour.Value = 0;
                    numericUpDown_Minute.Value = 0;
                    comboBox_Freq.SelectedIndex = 0;
                }
            }
            catch (Exception ex)
            {
                numericUpDown_Hour.Value = 0;
                numericUpDown_Minute.Value = 0;
                comboBox_Freq.SelectedIndex = 0;
            }
        }

        private void numericUpDown_Hour_ValueChanged(object sender, EventArgs e)
        {
            bt_ChangeSetting.Text = "更改";
        }

        private void comboBox_Freq_SelectedIndexChanged(object sender, EventArgs e)
        {
            bt_ChangeSetting.Text = "更改";
        }

        private void tabControl1_SelectedIndexChanged(object sender, EventArgs e)
        {
            bshowtouliao = false;
            bshowpasszone = false;
            bshowngzone = false;
            bshowfixstatus = false;

            if (tabControl1.SelectedIndex == 2)
            {
                bshowio = false;
                listBox5.Items.Clear();

                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    listBox5.Items.Add(Produce.Station.NameAll[i].ToString());
                }

                listBox5.SelectedIndex = 0;
            }

            else if (tabControl1.SelectedIndex == 3)
            {
                bshowio = false;
                if (tabControl6.SelectedIndex == 0)
                {
                    autoPanel_setgolden.Visible = false;
                    cBox_GoldenStation.Items.Clear();
                    cbox_goldenio.Items.Clear();
                    comboBox_StationName.Items.Clear();
                    autoPanel_Golden.Controls.Clear();

                    for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                    {
                        cBox_GoldenStation.Items.Add(Produce.Station.NameAll[i]);
                        comboBox_StationName.Items.Add(Produce.Station.NameAll[i]);
                    }
                    for (int j = 0; j < _myio.InputList.Count; j++)
                    {
                        cbox_goldenio.Items.Add(_myio.InputList[j].ToString());
                    }
                    if (Produce.Station.GoldenIOindex > _myio.InputList.Count)
                    {
                        Produce.SetGoldenIOindex(0);
                    }
                    cbox_goldenio.SelectedIndex = Produce.Station.GoldenIOindex - 1;

                    if (GoldenSampleStaion != "" && comboBox_StationName.Items.Contains(GoldenSampleStaion))
                    {
                        cBox_GoldenStation.SelectedItem = GoldenSampleStaion;
                    }
                    else
                    {
                        cBox_GoldenStation.SelectedIndex = 0;
                        GoldenSampleStaion = cBox_GoldenStation.SelectedItem.ToString();
                    }

                    comboBox_StationName.SelectedIndex = 0;
                    godenform = new YuLanForm();
                    godenform.Location = new Point(30, 10);
                    godenform.InitialYuLan();
                    autoPanel_Golden.Controls.Add(godenform);
                    for (int i = 0; i < Produce.Station.Count; i++)
                    {
                        if (allatsui1.ATS[i].bAlreadyTestGolden)
                        {
                            godenform.SetStation(i + 1, Color.Green);
                        }
                        else
                        {
                            godenform.SetStation(i + 1, Color.Gray);
                        }
                    }

                    autoPanel_setgolden.Visible = true;
                }
            }
            else if (tabControl1.SelectedIndex == 4)
            {
                bshowio = true;
                if (tabControl3.SelectedIndex == 2)
                {
                    bshowfixstatus = true;
                }
            }

            else if (tabControl1.SelectedIndex == 6)
            {
                bshowio = false;
                cBox_RMStation.Items.Clear();
                cBox_RMFix.Items.Clear();
                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    cBox_RMStation.Items.Add(Produce.Station.NameAll[i]);
                }
                cBox_RMStation.SelectedIndex = 0;
            }
            else if (tabControl1.SelectedIndex == 5)
            {
                bshowio = false;

                comboBox_watchstation.Items.Clear();

                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    comboBox_watchstation.Items.Add(Produce.Station.NameAll[i]);
                }
                comboBox_watchstation.SelectedIndex = 0;

            }

            else
            {
                bshowio = false;
                if (tabControl1.SelectedIndex == 1 && tabControl2.SelectedIndex == 2)
                {
                    bshowtouliao = true;
                }
                if (tabControl1.SelectedIndex == 1 && tabControl2.SelectedIndex == 3)
                {
                    bshowpasszone = true;
                }
                if (tabControl1.SelectedIndex == 1 && tabControl2.SelectedIndex == 4)
                {
                    bshowngzone = true;
                }

            }
        }

        private void tabControl2_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (tabControl2.SelectedIndex == 1)
            {
                bshowtouliao = false;
                bshowpasszone = false;
                bshowngzone = false;
                panel_Youxianji.Visible = false;
                listBox2.Items.Clear();
                listBox3.Items.Clear();
                listBox4.Items.Clear();

                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    listBox2.Items.Add(Produce.Station.NameAll[i].ToString());
                }

                listBox2.SelectedIndex = 0;

                for (int j = 0; j < GroupArray.Count; j++)
                {
                    listBox3.Items.Add("群組" + GroupArray[j].ToString());
                }
                listBox3.SelectedIndex = 0;

                string settye = INI.ReadINI(Application.StartupPath + "\\Data", "Priority", "Config", "Set", "0");
                if (settye == "0")
                {
                    rbton_ByManual.Checked = true;
                }
                else
                {
                    rbton_ByFR.Checked = true;
                }

                panel_Youxianji.Visible = true;
            }
            else if (tabControl2.SelectedIndex == 2)
            {
                bshowtouliao = true;
                bshowpasszone = false;
                bshowngzone = false;
                autoPanel_touliao.Visible = false;

                listBox6.Items.Clear();

                for (int j = 0; j < GroupArray.Count; j++)
                {
                    listBox6.Items.Add("群組" + GroupArray[j].ToString());
                }
                listBox6.SelectedIndex = 0;
                autoPanel_touliao.Visible = true;
            }
            else if (tabControl2.SelectedIndex == 3)
            {
                bshowtouliao = false;
                bshowpasszone = true;
                bshowngzone = false;
                autoPanel_passzone.Visible = false;

                listBox7.Items.Clear();

                for (int j = 0; j < GroupArray.Count; j++)
                {
                    listBox7.Items.Add("群組" + GroupArray[j].ToString());
                }
                listBox7.SelectedIndex = 0;
                autoPanel_passzone.Visible = true;
            }
            else if (tabControl2.SelectedIndex == 4)
            {
                bshowtouliao = false;
                bshowpasszone = false;
                bshowngzone = true;
                autoPanel_ngzone.Visible = false;

                listBox8.Items.Clear();

                for (int j = 0; j < GroupArray.Count; j++)
                {
                    listBox8.Items.Add("群組" + GroupArray[j].ToString());
                }
                listBox8.SelectedIndex = 0;
                autoPanel_ngzone.Visible = true;
            }
            else
            {
                bshowtouliao = false;
            }
        }

        private void bt_Group_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int index = listBox2.SelectedIndex;
            string stationname = listBox2.SelectedItem.ToString();
            int SetGroup = Convert.ToInt16(nUpDown_Group.Value);
            for (int i = 0; i < Produce.Station.NameAll.Length; i++)
            {
                if (i < index)
                {
                    int front = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[i].ToString()]);
                    if (SetGroup < front)
                    {
                        MessageBox.Show("不可比前面站別群組級別低\r\n  請重新設置！", "群組設定錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        return;
                    }
                }
                else if (i > index)
                {
                    int after = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[i].ToString()]);
                    if (SetGroup > after)
                    {
                        MessageBox.Show("不可比後面站別群組級別高\r\n  請重新設置！", "群組設定錯誤", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        return;
                    }
                }
            }

            Log.AddManualLog("群組設定", stationname + "站變更群組", "", SetGroup.ToString());

            Produce.SetGroup(stationname, SetGroup);
            GroupArray.Clear();
            listBox3.Items.Clear();
            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                int Group = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[p].ToString()]);
                if (!GroupArray.Contains(Group))
                {
                    GroupArray.Add(Group);
                }

                if (GetGroupIndex(Produce.Station.NameAll[p].ToString()) == 0)
                {
                    Produce.SetWaitTestBuffer(Produce.Station.NameAll[p].ToString(), 0);
                }
            }

            for (int j = 0; j < GroupArray.Count; j++)
            {
                listBox3.Items.Add("群組" + GroupArray[j].ToString());
            }
            listBox3.SelectedIndex = 0;
        }

        private void listBox2_SelectedIndexChanged(object sender, EventArgs e)
        {
            int index = listBox2.SelectedIndex;
            tbox_name.Text = listBox2.SelectedItem.ToString();
            nUpDown_Group.Minimum = 0;
            nUpDown_Group.Maximum = index;
            nUpDown_Group.Value = Convert.ToDecimal(Produce.Station.Group[listBox2.SelectedItem.ToString()]);
        }

        private void listBox3_SelectedIndexChanged(object sender, EventArgs e)
        {
            listBox4.Items.Clear();

            nUpDown_Pro_ByGroup.Minimum = 0;
            nUpDown_Pro_ByGroup.Maximum = GroupArray.Count - 1;

            tbox_group.Text = listBox3.SelectedItem.ToString();


            int SelectGroup = Convert.ToInt16(listBox3.SelectedItem.ToString().Replace("群組", ""));
            try
            {
                nUpDown_Pro_ByGroup.Value = Convert.ToDecimal(Produce.Station.GroupPriority[SelectGroup]);
            }
            catch (Exception ex)
            {
                Produce.SetGroupPriority(SelectGroup, 0);
                nUpDown_Pro_ByGroup.Value = 0;
            }

            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                int Group = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[p].ToString()]);
                if (Group == SelectGroup)
                {
                    listBox4.Items.Add(Produce.Station.NameAll[p].ToString());
                }
            }

            listBox4.SelectedIndex = 0;
        }

        private void listBox4_SelectedIndexChanged(object sender, EventArgs e)
        {
            autoPanel12.Controls.Clear();
            string stationname = listBox4.SelectedItem.ToString();
            int[] stationlist = (int[])Produce.Station.NumberList[stationname];


            for (int i = 0; i < stationlist.Length; i++)
            {
                FixPriority fp = new FixPriority();
                fp.StationNumber = stationlist[i];
                try
                {
                    fp.Priority = Convert.ToInt32(Produce.Station.FixturePriority[stationlist[i]]);
                }
                catch (Exception ex)
                {
                    Produce.SetFixtruePriority(stationlist[i], 0);
                    fp.Priority = 0;
                }
                fp.Location = new Point(70, 10 + 30 * i);

                autoPanel12.Controls.Add(fp);
            }
        }

        private void bt_SetGroupPri_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }



            int group = Convert.ToInt16(listBox3.SelectedItem.ToString().Replace("群組", ""));
            int grouppri = Convert.ToInt32(nUpDown_Pro_ByGroup.Value);

            Log.AddManualLog("優先級設定", listBox3.SelectedItem.ToString() + "變更優先級", "", grouppri.ToString());

            Produce.SetGroupPriority(group, grouppri);
        }

        private void bt_AllOn_Click(object sender, EventArgs e)
        {
            for (int i = 0; i < Produce.Station.Count; i++)
            {
                if (!allatsui1.ATS[i].checkBox_Used.Checked)
                {
                    allatsui1.ATS[i].SetCheckBox(allatsui1.ATS[i].checkBox_Used, true);
                }
            }
        }

        private void bt_AllOff_Click(object sender, EventArgs e)
        {
            for (int i = 0; i < Produce.Station.Count; i++)
            {
                if (allatsui1.ATS[i].checkBox_Used.Checked)
                {
                    if (!Produce.QUEUE.Exist(Convert.ToString(i + 1)) && allatsui1.ATS[i].status != TestUI.Status.Testing)
                    {
                        allatsui1.ATS[i].SetCheckBox(allatsui1.ATS[i].checkBox_Used, false);
                    }
                }
            }
        }

        private void bt_SetGoldenStation_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (bt_SetGoldenStation.Text == "更改")
            {
                Log.AddManualLog("測試狀態", "更改標準件投料站別", GoldenSampleStaion, cBox_GoldenStation.SelectedItem.ToString());
                GoldenSampleStaion = cBox_GoldenStation.SelectedItem.ToString();
                bt_SetGoldenStation.Text = "已變更";

            }
        }

        private void cBox_GoldenStation_SelectedIndexChanged(object sender, EventArgs e)
        {
            bt_SetGoldenStation.Text = "更改";
        }

        private void rbton_ByManual_CheckedChanged(object sender, EventArgs e)
        {
            if (rbton_ByManual.Checked)
            {
                autoPanel12.Enabled = true;
                INI.WriteINI(Application.StartupPath + "\\Data", "Priority", "Config", "Set", "0");
            }
            else
            {
                autoPanel12.Enabled = false;
                INI.WriteINI(Application.StartupPath + "\\Data", "Priority", "Config", "Set", "1");
            }
        }

        private void bt_Start_Click(object sender, EventArgs e)
        {
            if (bt_Start.Enabled)
            {
                if (!bDoorOpend && sWarning == "安全門被打開,系統暫停")
                {
                    QuxiaoWarning();
                    //SetLabelTextCallback(lb_WarnMSG, "系統已暫停", Color.Yellow);
                }
                else
                {
                    if (bDoorOpend)
                    {
                        ShowWarmForm("安全門尚未關閉,無法開始");
                        return;
                    }
                }
                  

                Log.AddMainLog("");
                Log.AddMainLog(" *** 開始測試 *** ");
                Log.AddMainLog("");
                Log.AddManualLog("測試狀態", "點擊開始", "未開始", "已開始");

                bt_Start.Enabled = false;
                cBox_NoWarning.Checked = false;

                

                if (bRobotconnected && bRobotPaused)
                {
                    bRobotPaused = false;
                    Produce.Epson.SendSystemMsg_Only_Epson("$Continue");
                }

                bPaused = false;

               

                if (lb_WarnMSG.Text == "系統已暫停")
                {
                    SetLabelTextCallback(lb_WarnMSG, "無異常報警", Color.Cyan);
                }
            }
        }

        private void bt_Pause_Click(object sender, EventArgs e)
        {
            if (!bt_Start.Enabled)
            {
                Log.AddMainLog("");
                Log.AddMainLog(" === 測試暫停 === ");
                Log.AddMainLog("");
                Log.AddManualLog("測試狀態", "點擊暫停", "已開始", "已暫停");

                bPaused = true;
                bt_Start.Enabled = true;
                if (sWarning == "")
                {
                    SetLabelTextCallback(lb_WarnMSG, "系統已暫停", Color.Yellow);
                }
            }
        }

        private void bt_remote_Click(object sender, EventArgs e)
        {


            if (bt_remote.Enabled)
            {
                int FixNum = Convert.ToInt32(cBox_RMFix.Text);
                string IPAdress = allatsui1.ATS[FixNum - 1].IP;
                remoteip = IPAddress.Parse(IPAdress);
                rm = new RemoteControl();
                rm.UdpSendMsg(remoteip, "1", "Connect");
                Thread.Sleep(500);
                //接收广播*************************
                rm.Connect();
                //DateTime dt = DateTime.Now;
                //while (dt.AddSeconds(5) > DateTime.Now)
                //{
                //    if (rm.bConnected)
                //    {
                bDisConnectRemote = false;
                bt_remote.Enabled = false;
                if (sWarning == "")
                {
                    SetLabelTextCallback(lb_WarnMSG, "遠端監控已開啟", Color.Yellow);
                }
                //    }
                //    else
                //    {
                //        Thread.Sleep(50);
                //    }
                //}
            }
        }


        private void bt_remoteclose_Click(object sender, EventArgs e)
        {
            if (!bt_remote.Enabled)
            {
                rm.UdpSendMsg(remoteip, "2", "close");
                rm.Close();
                pbox_Remote.Image = null;
                bDisConnectRemote = true;
                bt_remote.Enabled = true;
                rm = null;

                if (lb_WarnMSG.Text == "遠端監控已開啟")
                {
                    SetLabelTextCallback(lb_WarnMSG, "無異常報警", Color.Cyan);
                }
            }
        }


        private void pbox_Remote_MouseMove(object sender, MouseEventArgs e)
        {
            if (!bDisConnectRemote)
            {
                remotepoint = e.Location;
                rm.UdpSendMsg(remoteip, "3", remotepoint.X.ToString() + "," + remotepoint.Y.ToString());
            }
        }



        private void cBox_RMStation_SelectedIndexChanged(object sender, EventArgs e)
        {
            cBox_RMFix.Items.Clear();
            string SelectStationName = cBox_RMStation.Text;
            int[] List = (int[])Produce.Station.NumberList[SelectStationName];

            for (int i = 0; i < List.Length; i++)
            {
                cBox_RMFix.Items.Add(List[i]);
            }
            cBox_RMFix.SelectedIndex = 0;
        }

        private void pbox_Remote_MouseDown(object sender, MouseEventArgs e)
        {
            this.bt_key.Focus();

            if (!bDisConnectRemote)
            {
                if (e.Button == MouseButtons.Left)
                {
                    rm.UdpSendMsg(remoteip, "4", "1");
                }
                else if (e.Button == MouseButtons.Right)
                {
                    rm.UdpSendMsg(remoteip, "4", "2");
                }
                else if (e.Button == MouseButtons.Middle)
                {
                    rm.UdpSendMsg(remoteip, "4", "3");
                }
            }
        }

        private void pbox_Remote_MouseUp(object sender, MouseEventArgs e)
        {
            if (!bDisConnectRemote)
            {
                if (e.Button == MouseButtons.Left)
                {
                    rm.UdpSendMsg(remoteip, "5", "1");
                }
                else if (e.Button == MouseButtons.Right)
                {
                    rm.UdpSendMsg(remoteip, "5", "2");
                }
                else if (e.Button == MouseButtons.Middle)
                {
                    rm.UdpSendMsg(remoteip, "5", "3");
                }
            }
        }

        private void pbox_Remote_MouseWheel(object sender, MouseEventArgs e)
        {
            if (!bDisConnectRemote)
            {
                rm.UdpSendMsg(remoteip, "6", "1");
            }
        }

        private void pbox_Remote_PreviewKeyDown(object sender, PreviewKeyDownEventArgs e)
        {
            e.IsInputKey = true;

            if (!bDisConnectRemote)
            {
                int keyvalue = e.KeyValue;
                rm.UdpSendMsg(remoteip, "7", keyvalue.ToString());
            }
        }


        private void bt_key_KeyUp(object sender, KeyEventArgs e)
        {
            if (!bDisConnectRemote)
            {
                int keyvalue = e.KeyValue;
                rm.UdpSendMsg(remoteip, "8", keyvalue.ToString());
            }
        }

        private void listBox5_SelectedIndexChanged(object sender, EventArgs e)
        {
            //int index = listBox5.SelectedIndex;
            autoPanel_WaitTest.Controls.Clear();
            autoPanel_Retest.Controls.Clear();

            string stationname = listBox5.SelectedItem.ToString();
            tBox_BufferStationName.Text = stationname;
            string bufferkind = Produce.Station.Buffer[stationname].ToString();
            int waitcount = Convert.ToInt32(Produce.Station.WaitTestBuffer[stationname]);
            int Recount = Convert.ToInt32(Produce.Station.ReTestBuffer[stationname]);
            int BufferFixNum = 0;
            string BufferSN = "NONE";

            if (GetGroupIndex(stationname) == 0)
            {
                Produce.SetWaitTestBuffer(stationname, 0);
            }

            if (bufferkind == "0")
            {
                cBox_BufferKind.SelectedIndex = 0;

                for (int i = 0; i < waitcount; i++)
                {
                    Produce.GetWaitTestInfo(stationname, i + 1, ref BufferFixNum, ref BufferSN);

                    NormalBuffer nbff = new NormalBuffer();
                    nbff.StationName = stationname;
                    nbff.BufferType = NormalBuffer._buffertype.WaitTest;
                    nbff.ID = i + 1;
                    nbff.Location = new Point(10, 10 + i * (nbff.Size.Height + 10));

                    nbff.FixNum = BufferFixNum;
                    nbff.SN = BufferSN;

                    autoPanel_WaitTest.Controls.Add(nbff);
                }

                for (int j = 0; j < Recount; j++)
                {
                    Produce.GetReTestInfo(stationname, j + 1, ref BufferFixNum, ref BufferSN);

                    NormalBuffer rbff = new NormalBuffer();
                    rbff.StationName = stationname;
                    rbff.BufferType = NormalBuffer._buffertype.Retest;
                    rbff.ID = j + 1;
                    rbff.Location = new Point(10, 10 + j * (rbff.Size.Height + 10));

                    rbff.FixNum = BufferFixNum;
                    rbff.SN = BufferSN;

                    autoPanel_Retest.Controls.Add(rbff);
                }


            }
            else
            {
                cBox_BufferKind.SelectedIndex = 1;
            }
        }

        private int GetGroupIndex(string StationName)
        {
            int StationGroup = Convert.ToInt32(Produce.Station.Group[StationName]);
            int GroupIndex = 0;
            for (int j = 0; j < Produce.Station.NameAll.Length; j++)
            {
                string _StationName = Produce.Station.NameAll[j].ToString();
                int nStationGroup = Convert.ToInt32(Produce.Station.Group[_StationName]);

                if (StationGroup == nStationGroup)
                {
                    if (_StationName == StationName)
                    {
                        break;
                    }
                    GroupIndex++;
                }
            }

            return GroupIndex;
        }

        private void bt_BufferSet_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            string stationname = listBox5.SelectedItem.ToString();
            string bufferkind = Produce.Station.Buffer[stationname].ToString();


            if (((Button)sender).Name == "bt_AddWaitBuffer")
            {
                if (GetGroupIndex(stationname) > 0)
                {
                    int waitcount = Convert.ToInt32(Produce.Station.WaitTestBuffer[stationname]);

                    if (bufferkind == "0")
                    {
                        NormalBuffer nbff = new NormalBuffer();
                        nbff.StationName = stationname;
                        nbff.BufferType = NormalBuffer._buffertype.WaitTest;
                        nbff.ID = waitcount + 1;
                        nbff.Location = new Point(10, 10 + waitcount * (nbff.Size.Height + 10));
                        Produce.SetWaitTestInfo(stationname, waitcount + 1, 0, "NONE");
                        autoPanel_WaitTest.Controls.Add(nbff);
                        Produce.SetWaitTestBuffer(stationname, waitcount + 1);
                    }

                }
                else
                {
                    ShowWarmForm("群組中首站無待測Buffer");
                }
            }
            else if (((Button)sender).Name == "bt_AddRetestBuffer")
            {

                int Recount = Convert.ToInt32(Produce.Station.ReTestBuffer[stationname]);

                if (bufferkind == "0")
                {
                    NormalBuffer rbff = new NormalBuffer();
                    rbff.StationName = stationname;
                    rbff.BufferType = NormalBuffer._buffertype.Retest;
                    rbff.ID = Recount + 1;
                    rbff.Location = new Point(10, 10 + Recount * (rbff.Size.Height + 10));
                    Produce.SetReTestInfo(stationname, Recount + 1, 0, "NONE");
                    autoPanel_Retest.Controls.Add(rbff);
                    Produce.SetReTestBuffer(stationname, Recount + 1);
                }
            }
            else if (((Button)sender).Name == "bt_DeleteWaitBuffer")
            {
                int waitcount = Convert.ToInt32(Produce.Station.WaitTestBuffer[stationname]);
                if (bufferkind == "0")
                {
                    if (waitcount > 0)
                    {
                        autoPanel_WaitTest.Controls.RemoveAt(waitcount - 1);
                        Produce.SetWaitTestInfo(stationname, waitcount - 1, 0, "NONE");
                        Produce.SetWaitTestBuffer(stationname, waitcount - 1);
                    }
                }
            }
            else if (((Button)sender).Name == "bt_DeleteRetestBuffer")
            {
                int Recount = Convert.ToInt32(Produce.Station.ReTestBuffer[stationname]);
                if (bufferkind == "0")
                {
                    if (Recount > 0)
                    {
                        autoPanel_Retest.Controls.RemoveAt(Recount - 1);
                        Produce.SetReTestInfo(stationname, Recount - 1, 0, "NONE");
                        Produce.SetReTestBuffer(stationname, Recount - 1);
                    }
                }
            }
        }

        private string WarningShowMsg = "";

        public void ShowWarmForm(string WarnMsg)
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
            Thread.Sleep(500);
            wf.Close();
        }

        private void cbox_testmode_SelectedIndexChanged(object sender, EventArgs e)
        {
            //if (!Produce.bLoginOK || Produce.UserLevel < 2)
            //{

            //    ShowWarmForm("未登录或用户权限不足!");
            //    return;
            //}
            bAlreadyQingLiaoEnd = false;
            if (cbox_testmode.SelectedIndex == 0)
            {

                Log.AddManualLog("測試狀態", "更改測試模式", this._testmode.ToString(), "正常模式");
                this._testmode = TestMode.Normal;
                cbox_testmode.ForeColor = Color.Black;
            }

            else if (cbox_testmode.SelectedIndex == 1)
            {
                Log.AddManualLog("測試狀態", "更改測試模式", this._testmode.ToString(), "清料模式");
                this._testmode = TestMode.QingLiao;
                cbox_testmode.ForeColor = Color.Red;
            }

            //else if (cbox_testmode.SelectedIndex == 2)
            //{

            //    Log.AddManualLog("測試狀態", "更改測試模式", this._testmode.ToString(), "清洗探針模式");
            //    this._testmode = TestMode.QingLiao;
            //}
        }

        Thread LoginTimeOutThread;
        private void button1_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK)
            {
                LoginForm _LOGIN = new LoginForm();
                _LOGIN.ShowDialog();

                if (Produce.bLoginOK)
                {
                    lb_Username.Text = Produce.LoginName;
                    lb_Username.ForeColor = Color.Cyan;
                    lb_UserJob.Text = Produce.UserJob;
                    lb_UserJob.ForeColor = Color.Cyan;
                    lb_UserLevel.Text = "Level-" + Produce.UserLevel.ToString();
                    lb_UserLevel.ForeColor = Color.Cyan;
                    SetButtonPic(bt_login, Properties.Resources.user);

                    Log.AddManualLog("用戶登錄", "登入", "未登入", "已手動登入");

                    LoginTimeOutThread = new Thread(new ThreadStart(LoginTimeOut));
                    LoginTimeOutThread.Start();
                }
            }
            else
            {
                Log.AddManualLog("用戶登錄", "登出", "已登入", "已手動退出");

                Produce.bLoginOK = false;
                Produce.LoginName = "";
                Produce.UserJob = "";
                Produce.UserLevel = 0;

                lb_Username.Text = "未登錄";
                lb_Username.ForeColor = Color.SteelBlue;
                lb_UserJob.Text = "未知";
                lb_UserJob.ForeColor = Color.SteelBlue;
                lb_UserLevel.Text = "未知";
                lb_UserLevel.ForeColor = Color.SteelBlue;
                SetButtonPic(bt_login, Properties.Resources.LogOut);
                try
                {
                    if (LoginTimeOutThread.IsAlive)
                    {
                        LoginTimeOutThread.Abort();
                    }
                }
                catch (Exception ex)
                { }

            }
        }

        public void LoginTimeOut()
        {
            Thread.Sleep(Produce.LoginTimeOut * 60000);
            if (Produce.bLoginOK)
            {
                Log.AddManualLog("用戶登錄", "登出", "已登入", "超時" + Produce.LoginTimeOut.ToString() + "分鐘自動退出");
                Produce.bLoginOK = false;
                Produce.LoginName = "";
                Produce.UserJob = "";
                Produce.UserLevel = 0;

                SetLabelTextCallback(lb_Username, "未登錄", Color.SteelBlue);
                SetLabelTextCallback(lb_UserJob, "未知", Color.SteelBlue);
                SetLabelTextCallback(lb_UserLevel, "未知", Color.SteelBlue);
                SetButtonPic(bt_login, Properties.Resources.LogOut);

            }
        }

        private void 登錄設置ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            UserSet us = new UserSet();
            us.Show();
        }

        private void button10_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
        }

        private void toolStripMenuItem1_Click(object sender, EventArgs e)
        {
            SystemSetting syset = new SystemSetting();
            syset.Show();
        }

        private void bt_addinput_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (_myio.MyIOName == MyIO.IOType.YanHua)
            {
                SetIO _sio = new SetIO();
                _sio.ID = _myio.InputCount + 1;
                _sio.IOSet = SetIO.IOs.Input;
                _sio.Location = new Point(MousePosition.X - 150, MousePosition.Y - 300);
                if (DialogResult.OK == _sio.ShowDialog())
                {

                    Thread.Sleep(100);
                    string[] inmsg = _myio.InputList[_myio.InputCount - 1].ToString().Split(',');

                    OvalShape ovs = new OvalShape();
                    ShapeContainer st = new ShapeContainer();

                    ovs.BackStyle = Microsoft.VisualBasic.PowerPacks.BackStyle.Opaque;
                    ovs.BorderColor = System.Drawing.Color.Indigo;
                    ovs.BorderWidth = 4;
                    ovs.FillColor = System.Drawing.Color.Red;
                    ovs.FillGradientColor = System.Drawing.Color.Gold;
                    ovs.FillGradientStyle = Microsoft.VisualBasic.PowerPacks.FillGradientStyle.Central;
                    ovs.FillStyle = Microsoft.VisualBasic.PowerPacks.FillStyle.Solid;
                    ovs.Location = new System.Drawing.Point(59, 82);
                    ovs.Size = new System.Drawing.Size(35, 35);
                    ovs.Location = new Point(60, (_myio.InputCount - 1) * 62 + 24);

                    st.Location = new Point(0, 0);
                    st.Margin = new System.Windows.Forms.Padding(0);
                    st.Shapes.AddRange(new Microsoft.VisualBasic.PowerPacks.Shape[] { ovs });
                    st.Size = new System.Drawing.Size(290, 426);
                    st.TabIndex = 0;
                    st.TabStop = false;

                    Label lb = new Label();
                    lb.Text = inmsg[0];
                    lb.AutoSize = true;
                    lb.Location = new Point(120, (_myio.InputCount - 1) * 62 + 28);

                    autoPanel_input.Controls.Add(st);
                    autoPanel_input.Controls.Add(lb);
                }
            }
            else if (_myio.MyIOName == MyIO.IOType.Epson)
            {
                SetEpsonIO _sio = new SetEpsonIO();
                _sio.ID = _myio.InputCount + 1;
                _sio.IOSet = SetEpsonIO.IOs.Input;
                _sio.Location = new Point(MousePosition.X - 150, MousePosition.Y - 300);
                if (DialogResult.OK == _sio.ShowDialog())
                {

                    Thread.Sleep(100);
                    string[] inmsg = _myio.InputList[_myio.InputCount - 1].ToString().Split(',');

                    OvalShape ovs = new OvalShape();
                    ShapeContainer st = new ShapeContainer();

                    ovs.BackStyle = Microsoft.VisualBasic.PowerPacks.BackStyle.Opaque;
                    ovs.BorderColor = System.Drawing.Color.Indigo;
                    ovs.BorderWidth = 4;
                    ovs.FillColor = System.Drawing.Color.Red;
                    ovs.FillGradientColor = System.Drawing.Color.Gold;
                    ovs.FillGradientStyle = Microsoft.VisualBasic.PowerPacks.FillGradientStyle.Central;
                    ovs.FillStyle = Microsoft.VisualBasic.PowerPacks.FillStyle.Solid;
                    ovs.Location = new System.Drawing.Point(59, 82);
                    ovs.Size = new System.Drawing.Size(35, 35);
                    ovs.Location = new Point(60, (_myio.InputCount - 1) * 62 + 24);

                    st.Location = new Point(0, 0);
                    st.Margin = new System.Windows.Forms.Padding(0);
                    st.Shapes.AddRange(new Microsoft.VisualBasic.PowerPacks.Shape[] { ovs });
                    st.Size = new System.Drawing.Size(290, 426);
                    st.TabIndex = 0;
                    st.TabStop = false;

                    Label lb = new Label();
                    lb.Text = inmsg[0];
                    lb.AutoSize = true;
                    lb.Location = new Point(120, (_myio.InputCount - 1) * 62 + 28);

                    autoPanel_input.Controls.Add(st);
                    autoPanel_input.Controls.Add(lb);
                }
            }
        }




        private void bt_addoutput_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (_myio.MyIOName == MyIO.IOType.YanHua)
            {
                SetIO _sio = new SetIO();
                _sio.ID = _myio.OutputCount + 1;
                _sio.IOSet = SetIO.IOs.Output;
                _sio.Location = new Point(MousePosition.X - 150, MousePosition.Y - 300);
                if (DialogResult.OK == _sio.ShowDialog())
                {

                    Thread.Sleep(100);
                    string[] outmsg = _myio.OutputList[_myio.OutputCount - 1].ToString().Split(',');

                    UserSwitch usw = new UserSwitch();
                    usw.Location = new Point(50, (_myio.OutputCount - 1) * 62 + 10);
                    usw.Click += this.userswitch_click;
                    usw.Tag = _myio.OutputCount;

                    Label lb = new Label();
                    lb.Text = outmsg[0];
                    lb.AutoSize = true;
                    lb.Location = new Point(120, (_myio.OutputCount - 1) * 62 + 28);

                    autoPanel_output.Controls.Add(usw);
                    autoPanel_output.Controls.Add(lb);
                }
            }
            else if (_myio.MyIOName == MyIO.IOType.Epson)
            {
                SetEpsonIO _sio = new SetEpsonIO();
                _sio.ID = _myio.OutputCount + 1;
                _sio.IOSet = SetEpsonIO.IOs.Output;
                _sio.Location = new Point(MousePosition.X - 150, MousePosition.Y - 300);
                if (DialogResult.OK == _sio.ShowDialog())
                {

                    Thread.Sleep(100);
                    string[] outmsg = _myio.OutputList[_myio.OutputCount - 1].ToString().Split(',');

                    UserSwitch usw = new UserSwitch();
                    usw.Location = new Point(50, (_myio.OutputCount - 1) * 62 + 10);
                    usw.Click += this.userswitch_click;
                    usw.Tag = _myio.OutputCount;

                    Label lb = new Label();
                    lb.Text = outmsg[0];
                    lb.AutoSize = true;
                    lb.Location = new Point(120, (_myio.OutputCount - 1) * 62 + 28);

                    autoPanel_output.Controls.Add(usw);
                    autoPanel_output.Controls.Add(lb);
                }
            }
        }

        private void bt_deleteoutput_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (_myio.OutputCount > 0)
            {
                _myio.DeleteOutput();

                autoPanel_output.Controls.RemoveAt(autoPanel_output.Controls.Count - 1);
                autoPanel_output.Controls.RemoveAt(autoPanel_output.Controls.Count - 1);
            }

        }

        private void bt_deleteinput_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (_myio.InputCount > 0)
            {
                _myio.DeleteInput();

                autoPanel_input.Controls.RemoveAt(autoPanel_input.Controls.Count - 1);
                autoPanel_input.Controls.RemoveAt(autoPanel_input.Controls.Count - 1);
            }
        }


        private int send_202_out = 0;
        private bool b_202_status = false;
        private void userswitch_click(object sender, EventArgs e)
        {

            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int tag = Convert.ToInt32(((UserSwitch)sender).Tag);

            if (_myio.ReadOutput(tag - 1) != 1)// (((UserSwitch)sender).SwitchStatus)
            {
                Log.AddManualLog("手臂狀態", "設置輸出IO:" + Convert.ToString(tag - 1) + "_" + autoPanel_output.Controls[tag * 2 - 1].Text, "off", "on");

                send_202_out = tag - 1;
                b_202_status = true;

                Thread ths1 = new Thread(new ThreadStart(Send202));
                ths1.Start();

            }
            else
            {
                Log.AddManualLog("手臂狀態", "設置輸出IO:" + Convert.ToString(tag - 1) + "_" + autoPanel_output.Controls[tag * 2 - 1].Text, "on", "off");

                send_202_out = tag - 1;
                b_202_status = false;

                Thread ths1 = new Thread(new ThreadStart(Send202));
                ths1.Start();

            }
        }

        private void Send202()
        {
            _myio.SetOutput(send_202_out, b_202_status);
        }

        private void listBox6_SelectedIndexChanged(object sender, EventArgs e)
        {
            autoPanel_SetTouliao.Controls.Clear();
            tBox_toliaogroup.Text = listBox6.SelectedItem.ToString();
            int SelectGroup = Convert.ToInt16(listBox6.SelectedItem.ToString().Replace("群組", ""));
            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                int Group = Convert.ToInt16(Produce.Station.Group[Produce.Station.NameAll[p].ToString()]);
                if (Group == SelectGroup)
                {
                    tBox_toliaofirst.Text = Produce.Station.NameAll[p].ToString();
                    break;
                }
            }

            int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + SelectGroup.ToString()]);
            for (int i = 0; i < count; i++)
            {
                NormalTouLiao ntl = new NormalTouLiao();
                ntl.Group = SelectGroup;
                ntl.ID = i + 1;
                for (int j = 0; j < _myio.InputList.Count; j++)
                {
                    ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
                }
                int ioindex = Convert.ToInt32(Produce.Station.TouLiaoIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
                if (ntl.IOIndex > _myio.InputList.Count)
                {
                    Produce.SetTouLiao(SelectGroup, ntl.ID, 0);
                    ntl.IOIndex = 0;
                }
                else
                {
                    ntl.IOIndex = ioindex;
                }
                ntl.Location = new Point(100, 10 + i * 110);

                autoPanel_SetTouliao.Controls.Add(ntl);
            }


        }

        private void bt_addtouliao_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox6.SelectedIndex;
            Produce.AddTouLiao(SelectGroup, 0);


            NormalTouLiao ntl = new NormalTouLiao();
            ntl.Group = SelectGroup;
            ntl.ID = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + SelectGroup.ToString()]);

            for (int j = 0; j < _myio.InputList.Count; j++)
            {
                ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
            }
            ntl.IOIndex = Convert.ToInt32(Produce.Station.TouLiaoIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
            ntl.Location = new Point(100, 10 + (ntl.ID - 1) * 110);


            autoPanel_SetTouliao.Controls.Add(ntl);
        }

        private void bt_deletetouliao_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox6.SelectedIndex;
            int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + SelectGroup.ToString()]);
            if (count > 0)
            {
                Produce.DeleteTouLiao(SelectGroup);
                autoPanel_SetTouliao.Controls.RemoveAt(autoPanel_SetTouliao.Controls.Count - 1);
            }
        }

        private void bt_changegoldenio_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Produce.SetGoldenIOindex(cbox_goldenio.SelectedIndex + 1);
        }

        private void bt_NG_Click(object sender, EventArgs e)
        {
            dataGridView1.DataSource = null;
            lb_Count.Text = "0";
            string selecttime = dateTimePicker1.Value.ToString("yyyyMMdd");
            string selectstation = comboBox_watchstation.SelectedItem.ToString();
            string sFile = "";
            switch (((Button)sender).Name)
            {
                case "bt_NG":
                    lb_shengchan.Text = "不良記錄";
                    sFile = Application.StartupPath + "\\Log\\NG\\" + selectstation + "_NG_" + selecttime + ".csv";
                    break;

                case "bt_warn":
                    lb_shengchan.Text = "Warning記錄";
                    sFile = Application.StartupPath + "\\Log\\Warning\\" + selectstation + "_Warn_" + selecttime + ".csv";
                    break;

                case "bt_excep":
                    lb_shengchan.Text = "測試異常";
                    sFile = Application.StartupPath + "\\Log\\Exception\\" + selectstation + "_Exception_" + selecttime + ".csv";
                    break;

                case "bt_all":
                    lb_shengchan.Text = "所有記錄";
                    sFile = Application.StartupPath + "\\Log\\DUT\\" + selectstation + "_All_" + selecttime + ".csv";
                    break;
            }

            if (File.Exists(sFile))
            {
                DataTable dt = AutoMationTest.Function.CSVhelper.csv2dt(sFile, 0);
                dataGridView1.DataSource = dt;
                lb_Count.Text = dt.Rows.Count.ToString();
                dataGridView1.CurrentCell = dataGridView1[0, dataGridView1.Rows.Count - 1];
            }
        }

        private void bt_error_Click(object sender, EventArgs e)
        {
            dataGridView2.DataSource = null;
            lb_count2.Text = "0";
            string selecttime = dateTimePicker2.Value.ToString("yyyyMMdd");
            string sFile = "";
            DataTable dt = new DataTable();
            switch (((Button)sender).Name)
            {
                case "bt_error":
                    lb_yichang.Text = "異常記錄";

                    sFile = Application.StartupPath + "\\Log\\RobotError\\" + "RobotError_" + selecttime + ".csv";
                    if (File.Exists(sFile))
                    {
                        dt = AutoMationTest.Function.CSVhelper.csv2dt(sFile, 0);
                    }
                    break;
                case "bt_code":
                    lb_yichang.Text = "異常代碼";
                    sFile = Application.StartupPath + "\\ErrorCode\\ErrorCode.csv";
                    if (File.Exists(sFile))
                    {
                        dt = AutoMationTest.Function.CSVhelper.csv2dt2(sFile, 0, Encoding.GetEncoding("big5"));
                    }
                    break;
                case "bt_manual":
                    lb_yichang.Text = "手動記錄";
                    sFile = Application.StartupPath + "\\Log\\Manual\\" + "Manual_" + selecttime + ".csv";
                    if (File.Exists(sFile))
                    {
                        dt = AutoMationTest.Function.CSVhelper.csv2dt(sFile, 0);
                    }
                    break;
            }

            if (File.Exists(sFile))
            {

                dataGridView2.DataSource = dt;

                dataGridView2.CurrentCell = dataGridView2[0, dataGridView2.Rows.Count - 1];
                if (((Button)sender).Name == "bt_manual")
                {
                    lb_count2.Text = Convert.ToString(dt.Rows.Count / 2);
                    for (int i = 0; i < dataGridView2.Rows.Count; i++)
                    {
                        if (i % 2 == 0)
                        {
                            dataGridView2.Rows[i].DefaultCellStyle.BackColor = Color.White;
                        }
                        else
                        {
                            dataGridView2.Rows[i].DefaultCellStyle.BackColor = Color.LightBlue;
                        }
                    }
                }
                else
                {
                    lb_count2.Text = dt.Rows.Count.ToString();
                }
            }
        }

        private void bt_log_Click(object sender, EventArgs e)
        {
            Thread thcklog = new Thread(new ThreadStart(CheckLog));
            thcklog.Start();
        }

        private void CheckLog()
        {
            ClearRichBox(richTextBox1);
            //richTextBox1.Clear();
            string selecttime = dateTimePicker3.Value.ToString("yyyyMMdd");
            string sFile = Application.StartupPath + "\\Log\\Main\\" + "MainLog_" + selecttime + ".txt";
            if (File.Exists(sFile))
            {
                string[] lines = File.ReadAllLines(sFile);
                for (int i = 0; i < lines.Length; i++)
                {
                    //richTextBox1.AppendText(lines[i] + "\r\n");
                    //richTextBox1.SelectedText = lines[i] + "\r\n";

                    SelectRichBoxText(richTextBox1, lines[i] + "\r\n");

                    if (i % 2 == 0)
                    {
                        //richTextBox1.SelectionBackColor = Color.DarkSlateGray  ;
                    }
                    else
                    {
                        //richTextBox1.SelectionBackColor = Color.DarkBlue;
                        SetRichBoxTextColor(richTextBox1, Color.DarkBlue);
                    }
                }

                //richTextBox1.ScrollToCaret();
                ScrollRichBox(richTextBox1);
            }
        }

        private void bt_connectrobot_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 2)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            Log.AddManualLog("設備", "改變手臂狀態", "", "連接");
            Thread th11 = new Thread(new ThreadStart(Coonectstart));
            th11.Start();
        }

        private void Coonectstart()
        {
            if (Robot.IsConnected)
                return;
            Produce.Epson.Connect();
        }

        private void disscoonet()
        {
            Produce.Epson.DisConnect();
        }



        private void bt_disconnectrobot_Click(object sender, EventArgs e)
        {
            //if (!Produce.bLoginOK || Produce.UserLevel < 2)
            //{
            //    ShowWarmForm("未登录或用户权限不足!");
            //    return;
            //}
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                return;
            }

            if (bt_disconnectrobot.Text == "急停")
            {
                Log.AddManualLog("設備", "改變手臂狀態", "", "急停");
                Produce.Epson.SendSystemMsg_Only_Epson("$Pause,0");
                bt_disconnectrobot.Text = "繼續";
            }
            else
            {
                Log.AddManualLog("設備", "改變手臂狀態", "", "繼續");
                Produce.Epson.SendSystemMsg_Only_Epson("$Continue,0");
                bt_disconnectrobot.Text = "急停";
            }
            //Thread th11 = new Thread(new ThreadStart(disscoonet));
            //th11.Start();
        }

        private void bt_gohome_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 2)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            Log.AddManualLog("設備", "改變手臂狀態", "", "回安全點");
            Thread th1 = new Thread(new ThreadStart(robothome));
            th1.Start();
        }

        private void robothome()
        {
            RobotCMD_NoCheckGoNoGo("gosafe,home,0,0,0,0,0,0", "gosafe_home_ok", 0);

            //Produce.Epson.SendCheckRobot("gosafe,home,0,0,0,0,0,0", "gosafe_home_ok", 0, true, ref roborerror);
        }



        private void BaoJingLED()
        {
            try
            {
                bBaojingEnd = false;
                //_myio.SetOutput(0, false);
                //_myio.SetOutput(1, false);

                while (true)
                {
                    if (!bSkipBaoJing)
                    {
                        _myio.SetOutput(0, true);
                        Thread.Sleep(700);
                        _myio.SetOutput(0, false);
                        Thread.Sleep(300);
                    }
                    else
                    {
                        Thread.Sleep(100);
                    }
                    if (bQuxiaoBaojing)
                    {
                        bBaojingEnd = true;
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.ToString());
            }
        }

        private void AddWarning(string Warn)
        {
            if (sWarning != Warn)
            {
                Produce.QuxiaoWarning = false;
                sWarning = Warn;
                Log.AddMainLog("報警信息:" + Warn);

                SetLabelTextCallback(lb_WarnMSG, Warn, Color.Red);

                if (BaojingThread != null)
                {
                    if (!BaojingThread.IsAlive)
                    {
                        BaojingThread = new Thread(BaoJingLED);
                        BaojingThread.Start();
                    }
                }
                else
                {
                    BaojingThread = new Thread(BaoJingLED);
                    BaojingThread.Start();
                }

            }
        }

        private void QuxiaoWarning()
        {
            if (sWarning == "")
            {
                return;
            }

            sWarning = "";
            bQuxiaoBaojing = true;

            while (true)
            {
                if (bBaojingEnd)
                {
                    break;
                }
                Thread.Sleep(100);
            }


            //_myio.SetOutput(3, false);
            //_myio.SetOutput(2, false);
            _myio.SetOutput(0, false);

            bQuxiaoBaojing = false;

            SetLabelTextCallback(lb_WarnMSG, "無異常報警", Color.Cyan);

        }

        private void cBox_NoWarning_CheckedChanged(object sender, EventArgs e)
        {
            if (cBox_NoWarning.Checked)
                bSkipBaoJing = true;
            else
                bSkipBaoJing = false;
        }

        private void bt_clearwarning_Click(object sender, EventArgs e)
        {
            if (Produce.MainWarning != "")
            {
                Log.AddManualLog("異常處理", "取消報警", Produce.MainWarning.Replace(",", "-"), "取消");
                Produce.MainWarning = "";
                Produce.QuxiaoWarning = true;
                Thread quthread = new Thread(new ThreadStart(QuxiaoWarning));
                quthread.Start();

            }
        }
        QueueShow qs1;
        private void tabControl3_SelectedIndexChanged(object sender, EventArgs e)
        {
            bshowfixstatus = false;
            if (tabControl3.SelectedIndex == 1)
            {
                autoPanel_showqueque.Controls.Clear();
                qs1 = new QueueShow();
                qs1.Location = new Point(10, 10);
                autoPanel_showqueque.Controls.Add(qs1);
            }
            else if (tabControl3.SelectedIndex == 2)
            {
                autoPanel_fixture.Visible = false;

                if (Produce.bControlFixture)
                {
                    checkBox_fixcontrol.Checked = true;
                }
                else
                {
                    checkBox_fixcontrol.Checked = false;
                }

                listBox9.Items.Clear();

                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    listBox9.Items.Add(Produce.Station.NameAll[i].ToString());
                }

                listBox9.SelectedIndex = 0;

                autoPanel_fixture.Visible = true;
            }
        }

        private void bt_showqueue_Click(object sender, EventArgs e)
        {
            qs1.ShowStatus();
        }

        private void 關閉前信號ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            LastQueue last = new LastQueue();
            last.Show();
        }

        private void bt_openlog_Click(object sender, EventArgs e)
        {
            string selecttime = dateTimePicker3.Value.ToString("yyyyMMdd");
            string sFile = Application.StartupPath + "\\Log\\Main\\" + "MainLog_" + selecttime + ".txt";
            if (File.Exists(sFile))
            {
                Process.Start("Explorer.exe", sFile);
            }
        }

        private void cBox_skiptest_CheckedChanged(object sender, EventArgs e)
        {


            //if (!Produce.bLoginOK || Produce.UserLevel < 4)
            //{
            //    ShowWarmForm("未登录或用户权限不足!");


            //    return;
            //}

            if (cBox_skiptest.Checked)
            {
                Log.AddManualLog("測試狀態", "選擇跳過測試", "正常測試", "跳過測試");
                bskiptest = true;
            }
            else
            {
                Log.AddManualLog("測試狀態", "取消跳過測試", "跳過測試", "正常測試");
                bskiptest = false;
            }
        }

        private void bt_clearcount_Click(object sender, EventArgs e)
        {

            for (int i = 0; i < Produce.Station.Count; i++)
            {
                allatsui1.ATS[i].PassCount = 0;
                allatsui1.ATS[i].NGCount = 0;
                allatsui1.ATS[i].WarningCount = 0;

                string sStationNum = Convert.ToString(i + 1);

                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Pass", "0");
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "NG", "0");
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Warning", "0");
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "Fix_" + sStationNum, "Total", "0");


                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Pass", Produce.PassDUTCount.ToString());
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "NG", Produce.NGDUTCount.ToString());
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Warning", Produce.WarningDUTCount.ToString());
                INI.WriteINI(Application.StartupPath + "\\Data", "Test", "All", "Total", Produce.TotalDUTCount.ToString());
                Produce.PassDUTCount = 0;
                Produce.NGDUTCount = 0;
                Produce.WarningDUTCount = 0;
                Produce.TotalDUTCount = 0;

            }

        }

        private void 點位設置ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            //if (!Produce.bLoginOK || Produce.UserLevel < 5)
            //{
            //    ShowWarmForm("未登录或用户权限不足!");
            //    return;
            //}

            PointSetting pts = new PointSetting();
            pts.Show();
        }

        private void listBox7_SelectedIndexChanged(object sender, EventArgs e)
        {
            autoPanel_setpass.Controls.Clear();
            tBox_PassGroup.Text = listBox7.SelectedItem.ToString();
            int SelectGroup = Convert.ToInt16(listBox7.SelectedItem.ToString().Replace("群組", ""));


            int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + SelectGroup.ToString()]);
            for (int i = 0; i < count; i++)
            {
                NormalTouLiao ntl = new NormalTouLiao();
                ntl.FormType = NormalTouLiao.formtype.PassZone;
                ntl.Group = SelectGroup;
                ntl.ID = i + 1;
                for (int j = 0; j < _myio.InputList.Count; j++)
                {
                    ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
                }
                int ioindex = Convert.ToInt32(Produce.Station.PassZoneIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
                if (ntl.IOIndex > _myio.InputList.Count)
                {
                    Produce.SetPassZone(SelectGroup, ntl.ID, 0);
                    ntl.IOIndex = 0;
                }
                else
                {
                    ntl.IOIndex = ioindex;
                }
                ntl.Location = new Point(100, 10 + i * 110);

                autoPanel_setpass.Controls.Add(ntl);
            }
        }

        private void bt_addpasszone_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox7.SelectedIndex;
            Produce.AddPassZone(SelectGroup, 0);


            NormalTouLiao ntl = new NormalTouLiao();
            ntl.FormType = NormalTouLiao.formtype.PassZone;
            ntl.Group = SelectGroup;
            ntl.ID = Convert.ToInt32(Produce.Station.PassZoneIO["g" + SelectGroup.ToString()]);

            for (int j = 0; j < _myio.InputList.Count; j++)
            {
                ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
            }
            ntl.IOIndex = Convert.ToInt32(Produce.Station.PassZoneIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
            ntl.Location = new Point(100, 10 + (ntl.ID - 1) * 110);


            autoPanel_setpass.Controls.Add(ntl);
            autoPanel_setpass.Refresh();
        }

        private void bt_deletepasszone_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox7.SelectedIndex;
            int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + SelectGroup.ToString()]);
            if (count > 0)
            {
                Produce.DeletePassZone(SelectGroup);
                autoPanel_setpass.Controls.RemoveAt(autoPanel_setpass.Controls.Count - 1);
                autoPanel_setpass.Refresh();
            }
        }

        private void listBox8_SelectedIndexChanged(object sender, EventArgs e)
        {
            autoPanel_setng.Controls.Clear();
            tBox_ngGroup.Text = listBox8.SelectedItem.ToString();
            int SelectGroup = Convert.ToInt16(listBox8.SelectedItem.ToString().Replace("群組", ""));


            int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + SelectGroup.ToString()]);
            for (int i = 0; i < count; i++)
            {
                NormalTouLiao ntl = new NormalTouLiao();
                ntl.FormType = NormalTouLiao.formtype.NGZone;
                ntl.Group = SelectGroup;
                ntl.ID = i + 1;
                for (int j = 0; j < _myio.InputList.Count; j++)
                {
                    ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
                }
                int ioindex = Convert.ToInt32(Produce.Station.NGZoneIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
                if (ntl.IOIndex > _myio.InputList.Count)
                {
                    Produce.SetNGZone(SelectGroup, ntl.ID, 0);
                    ntl.IOIndex = 0;
                }
                else
                {
                    ntl.IOIndex = ioindex;
                }
                ntl.Location = new Point(100, 10 + i * 110);

                autoPanel_setng.Controls.Add(ntl);
            }
        }

        private void bt_addngzone_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox8.SelectedIndex;
            Produce.AddNGZone(SelectGroup, 0);


            NormalTouLiao ntl = new NormalTouLiao();
            ntl.FormType = NormalTouLiao.formtype.NGZone;
            ntl.Group = SelectGroup;
            ntl.ID = Convert.ToInt32(Produce.Station.PassZoneIO["g" + SelectGroup.ToString()]);

            for (int j = 0; j < _myio.InputList.Count; j++)
            {
                ntl.IOLIST.Items.Add(_myio.InputList[j].ToString());
            }
            ntl.IOIndex = Convert.ToInt32(Produce.Station.PassZoneIO["g" + SelectGroup.ToString() + "_" + ntl.ID.ToString()]);
            ntl.Location = new Point(100, 10 + (ntl.ID - 1) * 110);


            autoPanel_setng.Controls.Add(ntl);
            autoPanel_setng.Refresh();
        }

        private void bt_deletengzone_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            int SelectGroup = listBox8.SelectedIndex;
            int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + SelectGroup.ToString()]);
            if (count > 0)
            {
                Produce.DeleteNGZone(SelectGroup);
                autoPanel_setng.Controls.RemoveAt(autoPanel_setng.Controls.Count - 1);
                autoPanel_setng.Refresh();
            }
        }

        private void numericUpDown1_ValueChanged_1(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 2)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            Log.AddManualLog("手臂狀態", "更改手臂速度", "", numericUpDown1.Value.ToString());
            Thread threadspeed = new Thread(new ThreadStart(Setspeed));
            threadspeed.Start();
        }

        private void Setspeed()
        {
            Produce.Epson.SendCheckRobot("vspeed," + numericUpDown1.Value.ToString() + ",0,0,0,0,0,0", "vspeed_" + numericUpDown1.Value.ToString() + "_ok", 0, true, ref roborerror);
        }

        private void 手臂設置ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            Form_SetRobot frmsetrobot = new Form_SetRobot();
            frmsetrobot.Show();
        }

        private void bt_addhaocai_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Log.AddManualLog("耗材管控", "增加耗材數量", Produce.HaoCai.Count.ToString(), Convert.ToString(Produce.HaoCai.Count + 1));
            //if (Produce.HaoCai.Count > 0)
            //{
            dataGridView_haocai.Rows.Add();
            //}

            Produce.AddHaoCai();

            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[0].Value = Produce.HaoCai.Count.ToString();
            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[1].Value = Produce.HaoCai.Name[Produce.HaoCai.Count].ToString();

            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("吸嘴1吸真空");
            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("吸嘴2吸真空");
            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("手臂取放板");

            int toucount = 0;
            for (int j = 0; j < GroupArray.Count; j++)
            {
                int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[j].ToString()]);
                for (int k = 0; k < count; k++)
                {
                    toucount++;
                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("投料滑台_" + toucount.ToString() + "_送料");
                }

            }

            int pacount = 0;
            for (int j1 = 0; j1 < GroupArray.Count; j1++)
            {
                int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[j1].ToString()]);
                for (int k1 = 0; k1 < count; k1++)
                {
                    pacount++;
                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("PASS滑台_" + pacount.ToString() + "_出料");
                }

            }

            int ngcount = 0;
            for (int j2 = 0; j2 < GroupArray.Count; j2++)
            {
                int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[j2].ToString()]);
                for (int k2 = 0; k2 < count; k2++)
                {
                    ngcount++;
                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2]).Items.Add("NG滑台_" + ngcount.ToString() + "_出料");
                }

            }


            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[2].Value = Produce.HaoCai.HType[Produce.HaoCai.Count].ToString();



            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[3].Value = "更改";

            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[4].Value = "999999";
            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[5].Value = "更改";

            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[6].Value = "0";
            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[7].Value = "清空";

            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[8].Value = "0";
            dataGridView_haocai.Rows[Produce.HaoCai.Count - 1].Cells[9].Value = "清空";

            dataGridView_haocai.Refresh();
        }

        private void bt_deletehaocai_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (Produce.HaoCai.Count > 0)
            {
                Log.AddManualLog("耗材管控", "減少耗材數量", Produce.HaoCai.Count.ToString(), Convert.ToString(Produce.HaoCai.Count - 1));

                try
                {
                    Produce.DeleteHaoCai();
                    dataGridView_haocai.Rows.RemoveAt(Produce.HaoCai.Count);
                }
                catch (Exception ex)
                {
                    //MessageBox.Show(ex.ToString());
                }
            }
        }

        private void tabControl4_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (tabControl4.SelectedIndex == 3)
            {
                dataGridView_haocai.Rows.Clear();

                for (int i = 0; i < Produce.HaoCai.Count; i++)
                {
                    //if (i < Produce.HaoCai.Count - 1)
                    dataGridView_haocai.Rows.Add();

                    dataGridView_haocai.Rows[i].Cells[0].Value = Convert.ToString(i + 1);

                    dataGridView_haocai.Rows[i].Cells[1].Value = Produce.HaoCai.Name[i + 1].ToString();

                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("吸嘴1吸真空");
                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("吸嘴2吸真空");
                    ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("手臂取放板");

                    int toucount = 0;
                    for (int j = 0; j < GroupArray.Count; j++)
                    {
                        int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[j].ToString()]);
                        for (int k = 0; k < count; k++)
                        {
                            toucount++;
                            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("投料滑台_" + toucount.ToString() + "_送料");
                        }

                    }

                    int pacount = 0;
                    for (int j1 = 0; j1 < GroupArray.Count; j1++)
                    {
                        int count = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[j1].ToString()]);
                        for (int k1 = 0; k1 < count; k1++)
                        {
                            pacount++;
                            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("PASS滑台_" + pacount.ToString() + "_出料");
                        }

                    }

                    int ngcount = 0;
                    for (int j2 = 0; j2 < GroupArray.Count; j2++)
                    {
                        int count = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[j2].ToString()]);
                        for (int k2 = 0; k2 < count; k2++)
                        {
                            ngcount++;
                            ((DataGridViewComboBoxCell)dataGridView_haocai.Rows[i].Cells[2]).Items.Add("NG滑台_" + ngcount.ToString() + "_出料");
                        }

                    }


                    dataGridView_haocai.Rows[i].Cells[2].Value = Produce.HaoCai.HType[i + 1].ToString();


                    dataGridView_haocai.Rows[i].Cells[3].Value = "更改";

                    dataGridView_haocai.Rows[i].Cells[4].Value = Produce.HaoCai.Spec[i + 1].ToString();
                    dataGridView_haocai.Rows[i].Cells[5].Value = "更改";

                    dataGridView_haocai.Rows[i].Cells[6].Value = Produce.HaoCai.UseCount[i + 1].ToString();
                    dataGridView_haocai.Rows[i].Cells[7].Value = "清空";

                    dataGridView_haocai.Rows[i].Cells[8].Value = Produce.HaoCai.HistoryUseCount[i + 1].ToString();
                    dataGridView_haocai.Rows[i].Cells[9].Value = "清空";

                    double dusecount = Convert.ToDouble(Produce.HaoCai.UseCount[i + 1]);
                    double dspec = Convert.ToDouble(Produce.HaoCai.Spec[i + 1]);
                    if (dusecount >= dspec)
                    {
                        dataGridView_haocai.Rows[i].DefaultCellStyle.BackColor = Color.Red;
                    }

                }

            }
        }


        private void dataGridView_haocai_CellClick(object sender, DataGridViewCellEventArgs e)
        {
            if (e.RowIndex < 0 || (e.RowIndex == dataGridView_haocai.Rows.Count - 1))
            {
                return;
            }


            if (e.ColumnIndex == 3)//name
            {
                if (!Produce.bLoginOK || Produce.UserLevel < 5)
                {
                    ShowWarmForm("未登录或用户权限不足!");
                    return;
                }

                if (!bPaused)
                {
                    ShowWarmForm("程式運行中請勿操作!");
                    return;
                }

                Log.AddManualLog("耗材管控", "更改耗材名稱&類別", Produce.HaoCai.Name[e.RowIndex + 1].ToString() + ":" + Produce.HaoCai.HType[e.RowIndex + 1].ToString(), dataGridView_haocai.Rows[e.RowIndex].Cells[1].Value.ToString() + ":" + dataGridView_haocai.Rows[e.RowIndex].Cells[2].Value.ToString());

                Produce.ModifyHaoCai_NameType(e.RowIndex + 1, dataGridView_haocai.Rows[e.RowIndex].Cells[1].Value.ToString(), dataGridView_haocai.Rows[e.RowIndex].Cells[2].Value.ToString());
                dataGridView_haocai.Rows[e.RowIndex].DefaultCellStyle.BackColor = Color.Lime;
            }

            if (e.ColumnIndex == 5)
            {
                if (!Produce.bLoginOK || Produce.UserLevel < 5)
                {
                    ShowWarmForm("未登录或用户权限不足!");
                    return;
                }

                if (!bPaused)
                {
                    ShowWarmForm("程式運行中請勿操作!");
                    return;
                }

                double modifyspec = 0;
                try
                {
                    modifyspec = Convert.ToDouble(dataGridView_haocai.Rows[e.RowIndex].Cells[4].Value.ToString());
                }
                catch (Exception ex)
                {
                    ShowWarmForm("輸入的不是數字!");
                    return;
                }

                Log.AddManualLog("耗材管控", "更改耗材規格:" + Produce.HaoCai.Name[e.RowIndex + 1].ToString(), Produce.HaoCai.Spec[e.RowIndex + 1].ToString(), modifyspec.ToString());
                Produce.ModifyHaoCai_Spec(e.RowIndex + 1, modifyspec);
                dataGridView_haocai.Rows[e.RowIndex].DefaultCellStyle.BackColor = Color.Lime;
            }

            if (e.ColumnIndex == 7)
            {
                if (!Produce.bLoginOK || Produce.UserLevel < 5)
                {
                    ShowWarmForm("未登录或用户权限不足!");
                    return;
                }

                if (!bPaused)
                {
                    ShowWarmForm("程式運行中請勿操作!");
                    return;
                }
                Log.AddManualLog("耗材管控", "清空耗材使用計數:" + Produce.HaoCai.Name[e.RowIndex + 1].ToString(), Produce.HaoCai.UseCount[e.RowIndex + 1].ToString(), "0");
                Produce.ClearHaoCai_UseCount(e.RowIndex + 1);
                dataGridView_haocai.Rows[e.RowIndex].Cells[6].Value = "0";
                dataGridView_haocai.Rows[e.RowIndex].DefaultCellStyle.BackColor = Color.Lime;
            }

            if (e.ColumnIndex == 9)
            {
                if (!Produce.bLoginOK || Produce.UserLevel < 5)
                {
                    ShowWarmForm("未登录或用户权限不足!");
                    return;
                }

                if (!bPaused)
                {
                    ShowWarmForm("程式運行中請勿操作!");
                    return;
                }
                Log.AddManualLog("耗材管控", "清空耗材歷史使用計數:" + Produce.HaoCai.Name[e.RowIndex + 1].ToString(), Produce.HaoCai.UseCount[e.RowIndex + 1].ToString() + "-" + Produce.HaoCai.HistoryUseCount[e.RowIndex + 1].ToString(), "0-0");
                Produce.ClearHaoCai_HistoryUseCount(e.RowIndex + 1);
                dataGridView_haocai.Rows[e.RowIndex].Cells[6].Value = "0";
                dataGridView_haocai.Rows[e.RowIndex].Cells[8].Value = "0";
                dataGridView_haocai.Rows[e.RowIndex].DefaultCellStyle.BackColor = Color.Lime;
            }
        }

        private void dataGridView_haocai_CellValueChanged(object sender, DataGridViewCellEventArgs e)
        {

        }

        private void dataGridView_haocai_CellBeginEdit(object sender, DataGridViewCellCancelEventArgs e)
        {
            try
            {
                dataGridView_haocai.Rows[e.RowIndex].DefaultCellStyle.BackColor = Color.Purple;
            }
            catch (Exception ex)
            {

            }
        }

        private void tabControl6_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (tabControl6.SelectedIndex == 0)
            {
                autoPanel_setgolden.Visible = false;
                cBox_GoldenStation.Items.Clear();
                cbox_goldenio.Items.Clear();
                comboBox_StationName.Items.Clear();
                autoPanel_Golden.Controls.Clear();

                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    cBox_GoldenStation.Items.Add(Produce.Station.NameAll[i]);
                    comboBox_StationName.Items.Add(Produce.Station.NameAll[i]);
                }
                for (int j = 0; j < _myio.InputList.Count; j++)
                {
                    cbox_goldenio.Items.Add(_myio.InputList[j].ToString());
                }
                if (Produce.Station.GoldenIOindex > _myio.InputList.Count)
                {
                    Produce.SetGoldenIOindex(0);
                }
                cbox_goldenio.SelectedIndex = Produce.Station.GoldenIOindex - 1;

                if (GoldenSampleStaion != "" && comboBox_StationName.Items.Contains(GoldenSampleStaion))
                {
                    cBox_GoldenStation.SelectedItem = GoldenSampleStaion;
                }
                else
                {
                    cBox_GoldenStation.SelectedIndex = 0;
                    GoldenSampleStaion = cBox_GoldenStation.SelectedItem.ToString();
                }

                comboBox_StationName.SelectedIndex = 0;
                godenform = new YuLanForm();
                godenform.Location = new Point(30, 10);
                godenform.InitialYuLan();
                autoPanel_Golden.Controls.Add(godenform);
                for (int i = 0; i < Produce.Station.Count; i++)
                {
                    if (allatsui1.ATS[i].bAlreadyTestGolden)
                    {
                        godenform.SetStation(i + 1, Color.Green);
                    }
                    else
                    {
                        godenform.SetStation(i + 1, Color.Gray);
                    }
                }

                autoPanel_setgolden.Visible = true;
            }

            else if (tabControl6.SelectedIndex == 2)
            {
                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    cbox_grrstation.Items.Add(Produce.Station.NameAll[i]);
                }

                if (Produce.Station.GRR != "" && cbox_grrstation.Items.Contains(Produce.Station.GRR))
                {
                    cbox_grrstation.SelectedItem = Produce.Station.GRR;
                }
                else
                {
                    cbox_grrstation.SelectedIndex = -1;
                    Produce.SetGRRStation("");
                }

            }
            else if (tabControl6.SelectedIndex == 3)
            {
                autoPanel_tanzhen.Visible = false;
                bool bexist = false;
                cBox_tanzhenstation.Items.Clear();
                for (int i = 0; i < Produce.Station.NameAll.Length; i++)
                {
                    cBox_tanzhenstation.Items.Add(Produce.Station.NameAll[i]);
                }

                if (cBox_tanzhenstation.Items.Contains(Produce.Station.TanZhenStation))
                {
                    bexist = true;
                    cBox_tanzhenstation.SelectedItem = Produce.Station.TanZhenStation;
                }
                else
                {
                    cBox_tanzhenstation.SelectedIndex = -1;
                }

                for (int j = 0; j < _myio.InputList.Count; j++)
                {
                    cBox_tanzhenIO.Items.Add(_myio.InputList[j].ToString());
                }
                if (Produce.Station.TanZhenIOindex > _myio.InputList.Count)
                {
                    Produce.SetTanZhenIOindex(0);
                }
                cBox_tanzhenIO.SelectedIndex = Produce.Station.TanZhenIOindex - 1;

                autoPanel_settanzhen.Controls.Clear();
                if (bexist)
                {

                    for (int i = 0; i < ((int[])Produce.Station.NumberList[Produce.Station.TanZhenStation]).Length; i++)
                    {
                        CheckBox chbox = new CheckBox();
                        chbox.Text = Produce.Station.TanZhenStation + "-" + ((int[])Produce.Station.NumberList[Produce.Station.TanZhenStation])[i].ToString();
                        chbox.Location = new Point(20 + 140 * (i % 3), 50 + 50 * (i / 3));
                        autoPanel_settanzhen.Controls.Add(chbox);
                    }
                }

                autoPanel_tanzhen.Visible = true;
            }
        }

        private void listBox9_SelectedIndexChanged(object sender, EventArgs e)
        {
            SelectFixStation = listBox9.SelectedItem.ToString();
            tBox_fixselectstation.Text = SelectFixStation;

            autoPanel_fixstatus.Controls.Clear();

            int[] List = (int[])Produce.Station.NumberList[SelectFixStation];

            for (int i = 0; i < List.Length; i++)
            {
                FixtureControl fix = new FixtureControl();
                fix.StationNumber = List[i];

                fix.Location = new Point(10, 10 + 50 * i);
                autoPanel_fixstatus.Controls.Add(fix);
            }

            bshowfixstatus = true;
        }

        private void bt_changecontrolfix_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Log.AddManualLog("治具", "是否控制ATS治具", Produce.bControlFixture.ToString(), checkBox_fixcontrol.Checked.ToString());
            if (checkBox_fixcontrol.Checked)
            {
                Produce.SetControlFix(true);
            }
            else
            {
                Produce.SetControlFix(false);
            }
        }

        private void bt_setclearsocketstation_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Log.AddManualLog("清洗探針", "設置清洗探針站別", Produce.Station.TanZhenStation, cBox_tanzhenstation.SelectedItem.ToString());
            Produce.SetTanZhenStation(cBox_tanzhenstation.SelectedItem.ToString());
        }

        private void bt_setsocketio_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!bPaused)
            {
                ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Log.AddManualLog("清洗探針", "設置清洗探針IO", Produce.Station.TanZhenIOindex.ToString(), cBox_tanzhenIO.SelectedIndex.ToString());
            Produce.SetTanZhenIOindex(cBox_tanzhenIO.SelectedIndex + 1);
        }

        private void checkBox_openGRR_CheckedChanged(object sender, EventArgs e)
        {
            if (checkBox_openGRR.Checked)
            {
                if (Produce.Station.GRR == "")
                {
                    checkBox_openGRR.Checked = false;
                    ShowWarmForm("未設置GRR站別!");
                    return;
                }


                bGRRTest = true;
                Log.AddManualLog("測試狀態", "GRR測試", "正常模式", "開啟GRR模式");
                grrdutsn = new ArrayList();
                hs_fixtestcount = new Hashtable[Produce.GRR.DUTCount];
                hs_fixtestloopcount = new Hashtable[Produce.GRR.DUTCount];
                for (int i = 0; i < Produce.GRR.DUTCount; i++)
                {
                    hs_fixtestcount[i] = new Hashtable();
                    hs_fixtestloopcount[i] = new Hashtable();
                }

                int[] fixlist = (int[])Produce.Station.NumberList[Produce.Station.GRR];
                for (int j = 0; j < fixlist.Length; j++)
                {
                    listBox_grr.Items.Add("治具" + fixlist[j].ToString());
                }

                listBox_grr.SelectedIndex = 0;

                bt_changeGRRStation.Enabled = false;
                nUpDown_dutcount.Enabled = false;
                nUpDown_testcount.Enabled = false;
                nUpDown_loop.Enabled = false;

                nGRRTotalCount = fixlist.Length * Produce.GRR.DUTCount * Produce.GRR.TestCount * Produce.GRR.LoopCount;

                SetTextBoxCallback(tbox_grrloop, "0");
                SetTextBoxCallback(tbox_grrneedcount, nGRRTotalCount.ToString());
                SetTextBoxCallback(tbox_grrtestcount, "0");
                SetTextBoxCallback(tbox_notestcount, nGRRTotalCount.ToString());
            }
            else
            {
                bGRRTest = false;
                Log.AddManualLog("測試狀態", "GRR測試", "GRR模式", "關閉GRR模式");
                grrdutsn = null;
                hs_fixtestcount = null;
                hs_fixtestloopcount = null;
                listBox_grr.Items.Clear();
                dataGridView_GRR.Rows.Clear();

                bt_changeGRRStation.Enabled = true;
                nUpDown_dutcount.Enabled = true;
                nUpDown_testcount.Enabled = true;
                nUpDown_loop.Enabled = true;

                SetTextBoxCallback(tbox_grrloop, "");
                SetTextBoxCallback(tbox_grrneedcount, "");
                SetTextBoxCallback(tbox_grrtestcount, "");
                SetTextBoxCallback(tbox_notestcount, "");
            }
        }



        private string RobotGetSN()
        {
            return "";
        }

        private void GRRTest()
        {
            if (!bGRRTest)
            {
                return;
            }

            try
            {

                nGRRTotalCount = 0;
                testlist.Clear();
                string stationname = Produce.Station.GRR.ToString();
                int[] fixList = (int[])Produce.Station.NumberList[stationname];
                int dutindex = -1;// grrdutsn.IndexOf(Produce.RobotGetSN);
                DoingGroup = Convert.ToInt32(Produce.Station.Group[stationname]);

                if (!bRobotGetLiao)
                {
                    #region 讀碼 & 抓板
                    int touliaonum = -1;
                    bYouLiao = GetTouLiao(DoingGroup, ref touliaonum);

                    if (bYouLiao)
                    {
                        Produce.RobotGetSN = RobotGetSN();

                        if (!grrdutsn.Contains(Produce.RobotGetSN))
                        {
                            if (grrdutsn.Count < Produce.GRR.DUTCount)
                            {
                                grrdutsn.Add(Produce.RobotGetSN);
                                dutindex = grrdutsn.IndexOf(Produce.RobotGetSN);
                            }
                            else
                            {
                                Produce.MainWarning = "投放了超出設定的DUT數量";
                                Thread.Sleep(1000);
                                return;
                            }
                        }
                        else
                        {
                            dutindex = grrdutsn.IndexOf(Produce.RobotGetSN);
                            bool bdutcantest = false;
                            for (int k = 0; k < fixList.Length; k++)
                            {
                                if (allatsui1.ATS[fixList[k] - 1].checkBox_Used.Checked)
                                {
                                    int testcount = Convert.ToInt16(hs_fixtestcount[dutindex][fixList[k]]);
                                    if (testcount < Produce.GRR.TestCount)
                                    {
                                        //存在治具未測此DUT達到3次
                                        bdutcantest = true;
                                        //break;
                                    }

                                    int loopcount = Convert.ToInt16(hs_fixtestloopcount[dutindex][fixList[k]]);
                                    if (loopcount < Produce.GRR.LoopCount)
                                    {
                                        //治具測此DUT達到3次，但未測滿3圈
                                        bdutcantest = true;
                                        //break;
                                    }

                                    nGRRTotalCount++;

                                }
                            }

                            nGRRTotalCount = nGRRTotalCount * Produce.GRR.DUTCount * Produce.GRR.TestCount * Produce.GRR.LoopCount;

                            SetTextBoxCallback(tbox_grrneedcount, nGRRTotalCount.ToString());

                            if (!bdutcantest)
                            {
                                Produce.MainWarning = "此產品已被所有治具測試完成";
                                Thread.Sleep(1000);
                                return;
                            }
                        }


                        #region 投料滑台統計
                        for (int h = 0; h < Produce.HaoCai.Count; h++)
                        {
                            if (Produce.HaoCai.HType[h + 1].ToString().Contains("投料滑台_" + touliaonum.ToString()))
                            {
                                Produce.AddHaoCai_UseCount(h + 1);
                            }
                        }
                        #endregion

                        string tpara = "t" + touliaonum.ToString();
                        RobotCMD("laser," + tpara + "," + Produce.RobotPoint.Laser["投料點" + touliaonum.ToString() + "_Laser"].ToString(), "laser_" + tpara + "_ok", 0);
                        RobotCMD("pick," + tpara + "," + Produce.RobotPoint.Pick["投料點" + touliaonum.ToString() + "_Pick"].ToString(), "pick_" + tpara + "_ok", 0);
                        bRobotGetLiao = true;
                    }
                    #endregion

                    else
                    {
                        Thread.Sleep(1000);
                        return;
                    }

                }

                bool bExistSignal = false;

                #region 根據隊列中信號看是否有當站信號
                //根據隊列中信號的先後順序加入，更準確
                for (int m1 = 0; m1 < Produce.QUEUE.GetQueueLength(); m1++)
                {
                    int snum = Convert.ToInt32(Produce.QUEUE[m1].StationNumber);
                    int testcount = 0;
                    int testloopcount = 0;

                    if (hs_fixtestcount[dutindex].Contains(snum))
                    {
                        testcount = Convert.ToInt16(hs_fixtestcount[dutindex][snum]);
                        testloopcount = Convert.ToInt16(hs_fixtestloopcount[dutindex][snum]);
                    }
                    else
                    {
                        testcount = 0;
                        testloopcount = 0;
                        hs_fixtestcount[dutindex].Add(snum, 0);
                        hs_fixtestloopcount[dutindex].Add(snum, 0);
                    }

                    if (fixList.Contains(snum))
                    {
                        if (testcount < Produce.GRR.TestCount)
                        {
                            bExistSignal = true;

                            if (Produce.QUEUE[m1].robotCmd == Produce.RobotCMD.PASS)
                            {
                                hs_fixtestcount[dutindex][snum] = testcount++;
                                if (testcount == Produce.GRR.TestCount)
                                {
                                    hs_fixtestloopcount[dutindex][snum] = testloopcount++;
                                }
                            }
                        }
                        else
                        {
                            //已測滿3次
                            if (testloopcount < Produce.GRR.LoopCount)
                            {
                                //未測滿3圈
                                bExistSignal = true;

                                testcount = 0;
                                hs_fixtestcount[dutindex][snum] = testcount;

                                if (Produce.QUEUE[m1].robotCmd == Produce.RobotCMD.PASS)
                                {
                                    hs_fixtestcount[dutindex][snum] = testcount++;
                                }
                            }
                        }

                        testlist.Add(snum);
                        Addcombox(comboBox5, snum.ToString());
                        Addcombox(comboBox5, "NG區");
                        Log.AddMainLog("@@@@@@@@@@@@@@  GRR Test  @@@@@@@@@@@@@@");
                        Log.AddMainLog("  DUT[" + dutindex.ToString() + "]:" + Produce.RobotGetSN);
                        Log.AddMainLog("  FIX[" + snum.ToString() + "]  Loop:" + testloopcount.ToString() + ",Test:" + testcount.ToString());
                        Log.AddMainLog("@@@@@@@@@@@@@@  GRR Test  @@@@@@@@@@@@@@");

                        nGRRAlreadyCount++;
                        SetTextBoxCallback(tbox_grrloop, testloopcount.ToString());
                        SetTextBoxCallback(tbox_grrtestcount, nGRRAlreadyCount.ToString());
                        SetTextBoxCallback(tbox_notestcount, Convert.ToString(nGRRTotalCount - nGRRAlreadyCount));



                        break;
                    }
                }
                #endregion

                if (bExistSignal)
                {
                    RobotTest(testlist, DoingGroup);
                }
            }
            catch (Exception ex)
            {
                Produce.MainWarning = ex.Message;
                Log.AddMainLog("Exception:" + ex.ToString());
                Log.AddExceptionLog(Produce.RobotGetSN, ex.Message, 0);
                MessageBox.Show("Exception:" + ex.ToString());
            }
        }

        private void bt_changeGRRStation_Click(object sender, EventArgs e)
        {
            if (cbox_grrstation.SelectedIndex > -1)
            {
                Log.AddManualLog("模式設置", "更改GRR站別", Produce.Station.GRR, cbox_grrstation.SelectedItem.ToString());
                Produce.SetGRRStation(cbox_grrstation.SelectedItem.ToString());
            }
        }

        private void listBox_grr_SelectedIndexChanged(object sender, EventArgs e)
        {

            int fixnum = Convert.ToInt32(listBox_grr.SelectedItem.ToString().Replace("治具", ""));
            dataGridView_GRR.Rows.Clear();

            if (!allatsui1.ATS[fixnum - 1].checkBox_Used.Checked)
            {
                return;
            }

            if (bGRRTest)
            {

                int testcount = 0;
                int loopcount = 0;

                for (int i = 0; i < Produce.GRR.DUTCount; i++)
                {
                    dataGridView_GRR.Rows.Add();
                    dataGridView_GRR.Rows[i].Cells[0].Value = i.ToString();
                    if (grrdutsn.Count > i)
                    {
                        dataGridView_GRR.Rows[i].Cells[1].Value = grrdutsn[i].ToString();
                    }
                    else
                    {
                        dataGridView_GRR.Rows[i].Cells[1].Value = "";
                    }

                    if (hs_fixtestloopcount[i].Contains(fixnum))
                    {
                        loopcount = Convert.ToInt16(hs_fixtestloopcount[i][fixnum]);
                        dataGridView_GRR.Rows[i].Cells[2].Value = hs_fixtestloopcount[i][fixnum].ToString();
                    }
                    else
                    {
                        loopcount = 0;
                        dataGridView_GRR.Rows[i].Cells[2].Value = "0";
                    }

                    if (hs_fixtestcount[i].Contains(fixnum))
                    {
                        testcount = Convert.ToInt16(hs_fixtestcount[i][fixnum]);
                        dataGridView_GRR.Rows[i].Cells[3].Value = hs_fixtestcount[i][fixnum].ToString();
                    }
                    else
                    {
                        testcount = 0;
                        dataGridView_GRR.Rows[i].Cells[3].Value = "0";
                    }

                    if (loopcount == Produce.GRR.LoopCount)//&& testcount == Produce.GRR.TestCount)
                    {
                        dataGridView_GRR.Rows[i].Cells[4].Value = "Done";
                        dataGridView_GRR.Rows[i].DefaultCellStyle.BackColor = Color.Green;

                    }
                    else
                    {
                        dataGridView_GRR.Rows[i].Cells[4].Value = "OnGoing";
                        dataGridView_GRR.Rows[i].DefaultCellStyle.BackColor = Color.White;
                    }

                }

            }
        }

        private void nUpDown_dutcount_ValueChanged(object sender, EventArgs e)
        {
            try
            {
                int value = Convert.ToInt32(nUpDown_dutcount.Value);
                Produce.SetGRRDUTCount(value);
            }
            catch (Exception ex)
            {

            }
        }

        private void nUpDown_testcount_ValueChanged(object sender, EventArgs e)
        {
            try
            {
                int value = Convert.ToInt32(nUpDown_testcount.Value);
                Produce.SetGRRTestCount(value);
            }
            catch (Exception ex)
            {

            }
        }

        private void nUpDown_loop_ValueChanged(object sender, EventArgs e)
        {
            try
            {
                int value = Convert.ToInt32(nUpDown_loop.Value);
                Produce.SetGRRLoopCount(value);
            }
            catch (Exception ex)
            {

            }
        }

        private void 連接設置ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            Form_SetRobot frmsetrobot = new Form_SetRobot();
            frmsetrobot.Show();
        }

        private void 點位ToolStripMenuItem_Click(object sender, EventArgs e)
        {
            PointSetting pts = new PointSetting();
            pts.Show();
        }



    }
}
