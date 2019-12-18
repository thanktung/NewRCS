using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Collections;
using AutoMationTest.Robots;
using System.Threading;
using AutoMationTest.UI;
using AutoMationTest.Device;

namespace RobotMainForm
{
    public partial class PointSetting : Form
    {
        public PointSetting()
        {
            InitializeComponent();
        }

        #region Joy Stick para
        Thread thd_getjoystate;


        bool bXleft = false;
        bool bXright = false;
        bool bYup = false;
        bool bYdown = false;

        bool bZup = false;
        bool bZdown = false;

        bool bUup = false;
        bool bUdown = false;

        bool bRup = false;
        bool bRdown = false;

        bool bjoyon = false;
        string joydisvalue = "";

        bool bgop = false;
        bool bteach = false;
        bool bzk1 = false;
        bool bzk2 = false;

        bool bVWSwitched = false;
        string fuhao = "";
        int index = 0;
        #endregion

        private void RobotJoy()
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (bjoyon)
            {

                #region move axis
                if (bXleft || bXright || bYup || bYdown || bZup || bZdown || bUup || bUdown || bRup || bRdown)
                {
                    if (!bclicked)
                    {
                        bclicked = true;
                    }
                    else
                    {
                        return;
                    }
                    bup = false;

                    string error = "";
                    string head = "";

                    string point = "";

                    if (comboBox1.Text == "默认")
                    {
                        head = "movep,0";
                    }
                    else
                    {
                        head = "movej,0";
                    }

                    for (int i = 0; i < 6; i++)
                    {
                        if (i == index)
                        {
                            point += "," + fuhao + joydisvalue;
                        }
                        else
                        {
                            point += ",0";
                        }
                    }

                    SetTextBoxCallback(textMsgShow, head + point);
                    sendcmd = head + point;
                    checkcmd = head.Replace(",", "_") + "_ok";
                    Thread th1 = new Thread(new ThreadStart(SendCheck201));
                    th1.Start();

                    bclicked = false;
                }
                #endregion
            }

        }

        private void GoPosition()
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (bjoyon)
            {
                string point = "";
                string pointname = comboxPointName.SelectedItem.ToString();
                if (pointname.Contains("Pick"))
                {
                    point = Produce.RobotPoint.Pick[pointname].ToString();
                }
                else if (pointname.Contains("Put"))
                {
                    point = Produce.RobotPoint.Put[pointname].ToString();
                }
                else if (pointname.Contains("Laser"))
                {
                    point = Produce.RobotPoint.Laser[pointname].ToString();
                }
                string kk = "";
                if (pointname.Contains("治具"))
                {
                    kk = pointname.Split('_')[1];
                    if (kk.Length == 1)
                    {
                        kk = "0" + kk;
                    }
                }
                else if (pointname.Contains("投料點"))
                {
                    kk = "t" + pointname.Split('_')[2];
                }
                else if (pointname.Contains("標準件"))
                {
                    kk = "g";
                }
                else if (pointname.Contains("PASS"))
                {
                    kk = "p" + pointname.Split('_')[2];
                }
                else if (pointname.Contains("NG"))
                {
                    kk = "n" + pointname.Split('_')[2];
                }


                string pointup = "";
                string[] ssplit = point.Split(',');
                pointup = ssplit[0].Trim() + "," + ssplit[1].Trim() + "," + Convert.ToString(Convert.ToDouble(ssplit[2].Trim()) + 30) + "," + ssplit[3].Trim() + "," + ssplit[4].Trim() + "," + ssplit[5].Trim();

                SetTextBoxCallback(textMsgShow, "gop," + kk + "," + pointup);

                sendcmd = "gop," + kk + "," + pointup;
                checkcmd = "";
                Thread th1 = new Thread(new ThreadStart(SendCheck201));
                th1.Start();
            }
        }

        private void Teach()
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            string pname = comboxPointName.SelectedItem.ToString();
            string point = GetPosition();
            if (pname.Contains("Pick"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Pick[pname].ToString(), point);
            else if (pname.Contains("Put"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Put[pname].ToString(), point);
            else if (pname.Contains("Laser"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Laser[pname].ToString(), point);

            Produce.SetPoint(pname, point);

            int rowcount = comboxPointName.SelectedIndex;


            SetDataGridView(dataGridView1, rowcount, 1, point.Split(',')[0]);
            SetDataGridView(dataGridView1, rowcount, 2, point.Split(',')[1]);
            SetDataGridView(dataGridView1, rowcount, 3, point.Split(',')[2]);
            SetDataGridView(dataGridView1, rowcount, 4, point.Split(',')[3]);
            SetDataGridView(dataGridView1, rowcount, 5, point.Split(',')[4]);
            SetDataGridView(dataGridView1, rowcount, 6, point.Split(',')[5]);

            //dataGridView1.Rows[rowcount].Cells[2].Value = point.Split(',')[1];
            //dataGridView1.Rows[rowcount].Cells[3].Value = point.Split(',')[2];
            //dataGridView1.Rows[rowcount].Cells[4].Value = point.Split(',')[3];
            //dataGridView1.Rows[rowcount].Cells[5].Value = point.Split(',')[4];
            //dataGridView1.Rows[rowcount].Cells[6].Value = point.Split(',')[5];
        }

        private void Joystick()
        {
            try
            {
                while (true)
                {

                    Thread.Sleep(10);
                    if (JoyStickHelper.UpdateInfoEx() == 0)
                    {
                        bjoyon = true;
                        SetJianBianPanelColor(jog_status, Color.Lime, Color.FromArgb(0, 64, 0));
                    }
                    else
                    {
                        bjoyon = false;
                        SetJianBianPanelColor(jog_status, Color.WhiteSmoke, Color.Black);
                        continue;
                    }

                    //if (JoyStickHelper.ButtonDownState != 0)
                    //{
                    //    //SetAppendTextBoxCallback(textBox1, JoyStickHelper.ButtonDownState.ToString() + "\r\n");
                    //}
                    if (JoyStickHelper.ButtonState != 0)
                    {
                        if (JoyStickHelper.ButtonDownState == 256)
                        {
                            jogWheel1.ChangeStatus(AutoMationTest.UI.JogWheel.Status.ON);
                            bVWSwitched = true;
                            SetRadioButton(rb_W, true);
                        }
                        //else
                        //{
                        //    jogWheel1.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                        //    SetRadioButton(rb_V, true);
                        //}


                        if (JoyStickHelper.ButtonDownState == 512)
                        {
                            jogWheel2.ChangeStatus(AutoMationTest.UI.JogWheel.Status.ON);
                        }
                        //else
                        //{
                        //    jogWheel2.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                        //}




                        if (JoyStickHelper.ButtonDownState == 1)
                        {
                            joydisvalue = "0.1";
                            SetButtonColor(bt_01, Color.Yellow);
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_01, Color.WhiteSmoke );
                        //}
                        if (JoyStickHelper.ButtonDownState == 2)
                        {
                            joydisvalue = "1";
                            SetButtonColor(bt_1, Color.Yellow);
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_1, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 4)
                        {
                            joydisvalue = "100";
                            SetButtonColor(bt_100, Color.Yellow);
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_100, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 8)
                        {
                            joydisvalue = "10";
                            SetButtonColor(bt_10, Color.Yellow);
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_10, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 16)
                        {
                            bzk1 = true;
                            SetButtonColor(bt_zk1, Color.Yellow);
                            outnum = 1;
                            Thread th1 = new Thread(new ThreadStart(SendCheck202_Joy));
                            th1.Start();
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_zk1, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 32)
                        {
                            bzk2 = true;
                            SetButtonColor(bt_zk2, Color.Yellow);
                            outnum = 2;
                            Thread th1 = new Thread(new ThreadStart(SendCheck202_Joy));
                            th1.Start();
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_zk2, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 64)
                        {
                            bgop = true;
                            SetButtonColor(bt_gop, Color.Yellow);
                            Thread th1 = new Thread(new ThreadStart(GoPosition));
                            th1.Start();
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_gop, Color.WhiteSmoke);
                        //}
                        if (JoyStickHelper.ButtonDownState == 128)
                        {
                            bteach = true;
                            SetButtonColor(bt_teach, Color.Yellow);
                            Thread th1 = new Thread(new ThreadStart(Teach));
                            th1.Start();
                        }
                        //else
                        //{
                        //    SetButtonColor(bt_teach, Color.WhiteSmoke);
                        //}
                    }
                    else
                    {
                        bVWSwitched = false;
                        bzk1 = false;
                        bzk2 = false;
                        bgop = false;
                        bteach = false;
                        SetButtonColor(bt_01, Color.WhiteSmoke);
                        SetButtonColor(bt_1, Color.WhiteSmoke);
                        SetButtonColor(bt_10, Color.WhiteSmoke);
                        SetButtonColor(bt_100, Color.WhiteSmoke);
                        SetButtonColor(bt_zk1, Color.WhiteSmoke);
                        SetButtonColor(bt_zk2, Color.WhiteSmoke);
                        SetButtonColor(bt_gop, Color.WhiteSmoke);
                        SetButtonColor(bt_teach, Color.WhiteSmoke);
                        SetRadioButton(rb_V, true);
                        jogWheel1.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                        jogWheel2.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                    }
                    //if (JoyStickHelper.ButtonUpState != 0)
                    //{
                    //    //SetAppendTextBoxCallback(textBox1, JoyStickHelper.ButtonDownState.ToString() + "\r\n");
                    //    if (JoyStickHelper.ButtonDownState == 256)
                    //    {
                    //        jogWheel1.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                    //    }


                    //    if (JoyStickHelper.ButtonDownState == 512)
                    //    {
                    //        jogWheel2.ChangeStatus(AutoMationTest.UI.JogWheel.Status.OFF);
                    //    }

                    //}



                    #region Xleft
                    if (JoyStickHelper.AxisState[0] == 0)
                    {
                        if (!bXleft)
                        {
                            bXleft = true;
                            //SetAppendTextBoxCallback(textBox1, "X ←\r\n");
                            fuhao = "-";
                            index = 0;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Left);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bXleft)
                        {
                            bXleft = false;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }
                    #endregion

                    #region X right
                    if (JoyStickHelper.AxisState[0] == 65535)
                    {


                        if (!bXright)
                        {
                            bXright = true;
                            //SetAppendTextBoxCallback(textBox1, "X →\r\n");
                            fuhao = "";
                            index = 0;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Right);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bXright)
                        {
                            bXright = false;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }
                    #endregion

                    if (JoyStickHelper.AxisState[1] == 0)
                    {

                        if (!bYup)
                        {
                            bYup = true;
                            //SetAppendTextBoxCallback(textBox1, "Y ↑\r\n"); 
                            fuhao = "";
                            index = 1;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Up);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bYup)
                        {
                            bYup = false;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }

                    if (JoyStickHelper.AxisState[1] == 65535)
                    {

                        if (!bYdown)
                        {
                            bYdown = true;
                            fuhao = "-";
                            index = 1;
                            //SetAppendTextBoxCallback(textBox1, "Y ↓\r\n");
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Down);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bYdown)
                        {
                            bYdown = false;
                            jogWheel1.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }

                    if (JoyStickHelper.AxisState[2] == 128 || JoyStickHelper.AxisState[2] == 127)
                    {
                        if (!bZdown)
                        {
                            bZdown = true;
                            fuhao = "-";
                            if (bVWSwitched)
                            {
                                index = 5;
                            }
                            else
                            {
                                index = 4;
                            }
                            SetTrackbar(tbr_right, 0);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bZdown)
                        {
                            bZdown = false;
                            SetTrackbar(tbr_right, 1);
                        }
                    }

                    if (JoyStickHelper.AxisState[2] == 65408 || JoyStickHelper.AxisState[2] == 65407)
                    {
                        if (!bZup)
                        {
                            bZup = true;
                            fuhao = "";
                            if (bVWSwitched)
                            {
                                index = 5;
                            }
                            else
                            {
                                index = 4;
                            }
                            //SetAppendTextBoxCallback(textBox1, "Z ↑\r\n");
                            SetTrackbar(tbar_left, 0);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bZup)
                        {
                            bZup = false;
                            SetTrackbar(tbar_left, 1);
                        }
                    }


                    if (JoyStickHelper.AxisState[3] == 0)
                    {
                        if (!bUdown)
                        {
                            bUdown = true;
                            fuhao = "-";
                            index = 3;

                            //SetAppendTextBoxCallback(textBox1, "U ←\r\n");
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Left);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bUdown)
                        {
                            bUdown = false;
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }

                    if (JoyStickHelper.AxisState[3] == 65535)
                    {
                        if (!bUup)
                        {
                            bUup = true;
                            //SetAppendTextBoxCallback(textBox1, "U →\r\n");
                            fuhao = "";
                            index = 3;
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Right);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bUup)
                        {
                            bUup = false;
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }


                    #region R move


                    if (JoyStickHelper.AxisState[5] == 0)
                    {
                        if (!bRup)
                        {
                            bRup = true;
                            fuhao = "";
                            index = 2;
                            //SetAppendTextBoxCallback(textBox1, "R ↑\r\n");
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Up);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bRup)
                        {
                            bRup = false;
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }


                    if (JoyStickHelper.AxisState[5] == 65535)
                    {
                        if (!bRdown)
                        {
                            bRdown = true;
                            fuhao = "-";
                            index = 2;
                            //SetAppendTextBoxCallback(textBox1, "R ↓\r\n");
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Down);
                            Thread th1 = new Thread(new ThreadStart(RobotJoy));
                            th1.Start();
                        }
                    }
                    else
                    {
                        if (bRdown)
                        {
                            bRdown = false;
                            jogWheel2.Move(AutoMationTest.UI.JogWheel.Direction.Middle);
                        }
                    }

                    #endregion


                    //SetOVLocation(ovalShape2, leftPX, leftPY);
                }
            }
            catch (Exception ex)
            {

            }
        }

        delegate void dSetButtonColor(Button rbt, Color col);
        public void SetButtonColor(Button rbt, Color col)
        {
            try
            {
                if (rbt.InvokeRequired)
                {
                    dSetButtonColor d = new dSetButtonColor(SetButtonColor);
                    rbt.Invoke(d, new object[] { rbt, col });
                }
                else
                {
                    if (rbt.BackColor != col)
                        rbt.BackColor = col;
                }
            }
            catch (Exception ex)
            {

            }
        }

        delegate void dSetRadioButton(RadioButton rbt, bool bChecked);
        public void SetRadioButton(RadioButton rbt, bool bChecked)
        {
            try
            {
                if (rbt.InvokeRequired)
                {
                    dSetRadioButton d = new dSetRadioButton(SetRadioButton);
                    rbt.Invoke(d, new object[] { rbt, bChecked });
                }
                else
                {
                    if (rbt.Checked != bChecked)
                        rbt.Checked = bChecked;
                }
            }
            catch (Exception ex)
            {

            }
        }
        delegate void dSetTrackbar(TrackBar tbar, int value);
        public void SetTrackbar(TrackBar tbar, int value)
        {
            if (tbar.InvokeRequired)
            {
                dSetTrackbar d = new dSetTrackbar(SetTrackbar);
                tbar.Invoke(d, new object[] { tbar, value });
            }
            else
            {
                if (tbar.Value != value)
                    tbar.Value = value;

            }
        }

        delegate void dSetJianBianPanelColor(JianBianPanel panel, Color centercolor, Color surroundcolor);
        public void SetJianBianPanelColor(JianBianPanel panel, Color centercolor, Color surroundcolor)
        {
            try
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
            catch (Exception ex)
            { }
        }
        private void SendCheck202_Joy()
        {

            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }
            if (Program.mainform._myio.ReadOutput(outnum) == 0)
                Program.mainform._myio.SetOutput(outnum, true);
            else
                Program.mainform._myio.SetOutput(outnum, false);
        }

        private void PointSetting_Load(object sender, EventArgs e)
        {
            JobButtonText();
            listBox1.SelectedIndex = 0;

            comboxSafePoint.Items.Add("home_安全點");

            for (int j = 0; j < Produce.Station.Count; j++)
            {
                comboxSafePoint.Items.Add("治具_" + Convert.ToString(j + 1) + "_安全點");
            }

            ArrayList GroupArray = new ArrayList();
            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                string stationname = Produce.Station.NameAll[p].ToString();

                int Group = Convert.ToInt16(Produce.Station.Group[stationname]);
                if (!GroupArray.Contains(Group))
                {
                    GroupArray.Add(Group);
                }

            }

            for (int g = 0; g < GroupArray.Count; g++)
            {
                int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[g].ToString()]);
                for (int i = 0; i < count; i++)
                {
                    comboxSafePoint.Items.Add("投料點_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(i + 1) + "_" + "_安全點");

                }

                int count2 = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[g].ToString()]);
                for (int j = 0; j < count2; j++)
                {
                    comboxSafePoint.Items.Add("PASS區_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(j + 1) + "_" + "_安全點");
                }


                int count3 = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[g].ToString()]);
                for (int j = 0; j < count3; j++)
                {
                    comboxSafePoint.Items.Add("NG區_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(j + 1) + "_" + "_安全點");
                }
            }

            //comboxSafePoint.Items.Add("投料點_安全點");
            comboxSafePoint.Items.Add("標準件區_安全點");
            comboxSafePoint.Items.Add("PALL_安全點");
            comboxSafePoint.Items.Add("NALL_安全點");
            //comboxSafePoint.Items.Add("Pass區_安全點");
            //comboxSafePoint.Items.Add("NG區_安全點");

            thd_getjoystate = new Thread(new ThreadStart(Joystick));
            thd_getjoystate.Start();

        }

        private void JobButtonText()
        {
            if (!bzhoumove)
            {
                btn_1_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\X0.jpg");
                btn_1_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\X1.jpg");
                btn_2_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\Y0.jpg");
                btn_2_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\Y1.jpg");
                btn_3_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\Z0.jpg");
                btn_3_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\Z1.jpg");
                btn_4_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\U0.jpg");
                btn_4_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\U1.jpg");
                btn_5_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\V0.jpg");
                btn_5_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\V1.jpg");
                btn_6_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\W0.jpg");
                btn_6_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\W1.jpg");
            }
            else
            {
                btn_1_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J10.jpg");
                btn_1_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J11.jpg");
                btn_2_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J20.jpg");
                btn_2_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J21.jpg");
                btn_3_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J30.jpg");
                btn_3_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J31.jpg");
                btn_4_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J40.jpg");
                btn_4_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J41.jpg");
                btn_5_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J50.jpg");
                btn_5_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J51.jpg");
                btn_6_0.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J60.jpg");
                btn_6_1.Image = Image.FromFile(Application.StartupPath + "\\Pic\\J61.jpg");
            }
        }



        private void comboxPointName_SelectedIndexChanged(object sender, EventArgs e)
        {


        }

        private void listBox1_SelectedIndexChanged(object sender, EventArgs e)
        {
            comboxPointName.Items.Clear();
            dataGridView1.Rows.Clear();
            string name = "";
            string itemname = "";
            int rowcount = 0;
            switch (listBox1.SelectedIndex)
            {
                case 0:
                    name = "Pick";
                    break;
                case 1:
                    name = "Put";
                    break;
                case 2:
                    name = "Laser";
                    break;
            }

            for (int j = 0; j < Produce.Station.Count; j++)
            {

                itemname = "治具_" + Convert.ToString(j + 1) + "_" + name;
                string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                comboxPointName.Items.Add(itemname);
                dataGridView1.Rows.Add();

                dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                rowcount++;
            }


            ArrayList GroupArray = new ArrayList();
            for (int p = 0; p < Produce.Station.NameAll.Length; p++)
            {
                string stationname = Produce.Station.NameAll[p].ToString();

                int Group = Convert.ToInt16(Produce.Station.Group[stationname]);
                if (!GroupArray.Contains(Group))
                {
                    GroupArray.Add(Group);
                }

                int waitBuffCount = Convert.ToInt32(Produce.Station.WaitTestBuffer[stationname]);
                int retestBuffer = Convert.ToInt32(Produce.Station.ReTestBuffer[stationname]);

                for (int b1 = 0; b1 < waitBuffCount; b1++)
                {


                    itemname = stationname + "_待測Buffer_" + Convert.ToString(b1 + 1) + "_" + name;
                    string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                    comboxPointName.Items.Add(itemname);
                    dataGridView1.Rows.Add();
                    dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                    dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                    dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                    dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                    dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                    dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                    dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                    rowcount++;
                }

                for (int b2 = 0; b2 < retestBuffer; b2++)
                {


                    itemname = stationname + "_複測Buffer_" + Convert.ToString(b2 + 1) + "_" + name;
                    string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                    comboxPointName.Items.Add(itemname);
                    dataGridView1.Rows.Add();
                    dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                    dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                    dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                    dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                    dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                    dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                    dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                    rowcount++;
                }
            }
            for (int g = 0; g < GroupArray.Count; g++)
            {
                int count = Convert.ToInt32(Produce.Station.TouLiaoCount["g" + GroupArray[g].ToString()]);
                for (int i = 0; i < count; i++)
                {


                    itemname = "投料點_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(i + 1) + "_" + name;
                    string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                    comboxPointName.Items.Add(itemname);
                    dataGridView1.Rows.Add();
                    dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                    dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                    dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                    dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                    dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                    dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                    dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                    rowcount++;
                }

                int count2 = Convert.ToInt32(Produce.Station.PassZoneCount["g" + GroupArray[g].ToString()]);
                for (int j = 0; j < count2; j++)
                {

                    itemname = "PASS區_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(j + 1) + "_" + name;
                    string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                    comboxPointName.Items.Add(itemname);
                    dataGridView1.Rows.Add();
                    dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                    dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                    dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                    dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                    dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                    dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                    dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                    rowcount++;
                }


                int count3 = Convert.ToInt32(Produce.Station.NGZoneCount["g" + GroupArray[g].ToString()]);
                for (int j = 0; j < count3; j++)
                {

                    itemname = "NG區_" + "g" + GroupArray[g].ToString() + "_" + Convert.ToString(j + 1) + "_" + name;
                    string[] readvalue = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
                    comboxPointName.Items.Add(itemname);
                    dataGridView1.Rows.Add();
                    dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
                    dataGridView1.Rows[rowcount].Cells[1].Value = readvalue[0];
                    dataGridView1.Rows[rowcount].Cells[2].Value = readvalue[1];
                    dataGridView1.Rows[rowcount].Cells[3].Value = readvalue[2];
                    dataGridView1.Rows[rowcount].Cells[4].Value = readvalue[3];
                    dataGridView1.Rows[rowcount].Cells[5].Value = readvalue[4];
                    dataGridView1.Rows[rowcount].Cells[6].Value = readvalue[5];
                    rowcount++;
                }
            }


            itemname = "標準件區_" + name;

            string[] readvalue1 = INI.ReadINI(Application.StartupPath + "\\Data", "Point", name, itemname, "0,0,0,0,0,0").Split(',');
            comboxPointName.Items.Add(itemname);
            dataGridView1.Rows.Add();
            dataGridView1.Rows[rowcount].Cells[0].Value = itemname;
            dataGridView1.Rows[rowcount].Cells[1].Value = readvalue1[0];
            dataGridView1.Rows[rowcount].Cells[2].Value = readvalue1[1];
            dataGridView1.Rows[rowcount].Cells[3].Value = readvalue1[2];
            dataGridView1.Rows[rowcount].Cells[4].Value = readvalue1[3];
            dataGridView1.Rows[rowcount].Cells[5].Value = readvalue1[4];
            dataGridView1.Rows[rowcount].Cells[6].Value = readvalue1[5];
            rowcount++;


            comboxPointName.SelectedIndex = 0;
        }

        private void bt_motoron_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }
            Produce.Epson.SendSystemMsg_Only_Epson("$SetMotorsOn,0");
        }

        private void bt_motoroff_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                return;
            }
            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Produce.Epson.SendSystemMsg_Only_Epson("$SetMotorsOff,0");
        }

        private void bt_reset_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                return;
            }
            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            Produce.Epson.SendSystemMsg_Only_Epson("$Reset,0");
        }

        private void btnSetRobotAndMotorPoint_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            string pname = comboxPointName.SelectedItem.ToString();
            string point = GetPosition();
            if (pname.Contains("Pick"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Pick[pname].ToString(), point);
            else if (pname.Contains("Put"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Put[pname].ToString(), point);
            else if (pname.Contains("Laser"))
                Log.AddManualLog("數據", "更改手臂點位:" + pname, Produce.RobotPoint.Laser[pname].ToString(), point);

            Produce.SetPoint(pname, point);

            int rowcount = comboxPointName.SelectedIndex;


            dataGridView1.Rows[rowcount].Cells[1].Value = point.Split(',')[0];
            dataGridView1.Rows[rowcount].Cells[2].Value = point.Split(',')[1];
            dataGridView1.Rows[rowcount].Cells[3].Value = point.Split(',')[2];
            dataGridView1.Rows[rowcount].Cells[4].Value = point.Split(',')[3];
            dataGridView1.Rows[rowcount].Cells[5].Value = point.Split(',')[4];
            dataGridView1.Rows[rowcount].Cells[6].Value = point.Split(',')[5];

        }

        private string GetMoveDis()
        {
            if (radioButton1.Checked)
                return "0.1";
            else if (radioButton2.Checked)
                return "0.5";
            else if (radioButton3.Checked)
                return "1";
            else if (radioButton4.Checked)
                return "5";
            else if (radioButton5.Checked)
                return "10";
            else if (radioButton6.Checked)
                return "100";
            else
                return "0";
        }

        private void btn1A_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (!bclicked)
            {
                bclicked = true;
            }
            else
            {
                return;
            }
            bup = false;

            string error = "";
            string head = "";
            string fuhao = "";
            string point = "";
            string value = GetMoveDis();
            if (!bzhoumove)
            {
                head = "movep,0";
            }
            else
            {
                head = "movej,0";
            }

            string[] ssplit = ((Button)sender).Name.Split('_');
            int index = Convert.ToInt16(ssplit[1]) - 1;
            if (ssplit[2] == "0")
            {
                fuhao = "";
            }
            else
            {
                fuhao = "-";
            }

            for (int i = 0; i < 6; i++)
            {
                if (i == index)
                {
                    point += "," + fuhao + value;
                }
                else
                {
                    point += ",0";
                }
            }

            textMsgShow.Text = head + point;
            sendcmd = head + point;
            checkcmd = head.Replace(",", "_") + "_ok";
            Thread th1 = new Thread(new ThreadStart(SendCheck201));
            th1.Start();
            //Produce.Epson.SendCheckRobot(head + point, head.Replace(",", "_") + "_ok", 0, true, ref error);
            //GetPosition();
            bclicked = false;
        }

        private string sendcmd = "";
        private string checkcmd = "";
        private int outnum = 0;
        private bool bonoff = false;
        bool bup = false;
        private void SendCheck201()
        {
        again1:
            string error = "";
            if (Produce.Epson.SendCheckRobot(sendcmd, checkcmd, 0, true, ref error))
            {
                GetPosition();
            }
            else
            {
                AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.YesNo, Produce.RobotWarning);
                if (DialogResult.Retry == _warnForm.ShowDialog())
                {
                    Log.AddMainLog("[手動]選擇: 重試");
                    Produce.RobotWarning = "";
                    goto again1;
                }
                else
                {
                    Log.AddMainLog("[手動]選擇: 繼續");
                    Produce.RobotWarning = "";
                }
            }

        }

        private void SendCheck201cycle()
        {

            while (true)
            {

            again2:
                string error = "";
                if (Produce.Epson.SendCheckRobot(sendcmd, checkcmd, 0, true, ref error))
                {
                    GetPosition();
                }
                else
                {
                    AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.YesNo, Produce.RobotWarning);
                    if (DialogResult.Retry == _warnForm.ShowDialog())
                    {
                        Log.AddMainLog("[手動]選擇: 重試");
                        Produce.RobotWarning = "";
                        goto again2;
                    }
                    else
                    {
                        Log.AddMainLog("[手動]選擇: 繼續");
                        Produce.RobotWarning = "";
                    }
                }

                if (bup)
                {
                    break;
                }

            }

        }

        private void SendCheck202()
        {
            Program.mainform._myio.SetOutput(outnum, bonoff);
        }


        public string GetPosition()
        {
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                return "0,0,0,0,0,0";
            }

        again:

            string error = "";
            if (Produce.Epson.SendCheckRobot("readposition,0,0,0,0,0,0,0", ",ok", 0, true, ref error))
            {
                try
                {
                    string[] ssplit = Robot.ReceiveMSG_From_Robot.Split(':')[1].Replace("\r", "").Replace("\n", "").Trim().Split(',');
                    SetTextBoxCallback(textBoxX, ssplit[0].Trim());
                    SetTextBoxCallback(textBoxY, ssplit[1].Trim());
                    SetTextBoxCallback(textBoxZ, ssplit[2].Trim());
                    SetTextBoxCallback(textBoxU, ssplit[3].Trim());
                    SetTextBoxCallback(textBoxV, ssplit[4].Trim());
                    SetTextBoxCallback(textBoxW, ssplit[5].Trim());
                    return ssplit[0].Trim() + "," + ssplit[1].Trim() + "," + ssplit[2].Trim() + "," + ssplit[3].Trim() + "," + ssplit[4].Trim() + "," + ssplit[5].Trim();
                }
                catch (Exception ex)
                {
                    return "0,0,0,0,0,0";
                }
            }
            else
            {
                AutoMationTest.UI.RobotWarningForm _warnForm = new AutoMationTest.UI.RobotWarningForm(AutoMationTest.UI.RobotWarningForm.MessageButton.YesNo, Produce.RobotWarning);
                if (DialogResult.Retry == _warnForm.ShowDialog())
                {
                    Log.AddMainLog("[手動]選擇: 重試");
                    Produce.RobotWarning = "";
                    goto again;
                }
                else
                {
                    Log.AddMainLog("[手動]選擇: 繼續");
                    Produce.RobotWarning = "";
                }
                return "0,0,0,0,0,0";
            }
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

        delegate void dSetDataGridView(DataGridView dgv, int rownum, int cellnum, string text);
        public void SetDataGridView(DataGridView dgv, int rownum, int cellnum, string text)
        {
            if (dgv.InvokeRequired)
            {
                dSetDataGridView d = new dSetDataGridView(SetDataGridView);
                dgv.Invoke(d, new object[] { dgv, rownum, cellnum, text });
            }
            else
            {
                dgv.Rows[rownum].Cells[cellnum].Value = text;

            }
        }



        private void btnGoPosition_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (MessageBox.Show("确定进行走位？", "确认", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) == DialogResult.Yes)
            {
                string point = "";
                string pointname = comboxPointName.SelectedItem.ToString();
                if (pointname.Contains("Pick"))
                {
                    point = Produce.RobotPoint.Pick[pointname].ToString();
                }
                else if (pointname.Contains("Put"))
                {
                    point = Produce.RobotPoint.Put[pointname].ToString();
                }
                else if (pointname.Contains("Laser"))
                {
                    point = Produce.RobotPoint.Laser[pointname].ToString();
                }
                string kk = "";
                if (pointname.Contains("治具"))
                {
                    kk = pointname.Split('_')[1];
                    if (kk.Length == 1)
                    {
                        kk = "0" + kk;
                    }
                }
                else if (pointname.Contains("投料點"))
                {
                    kk = "t" + pointname.Split('_')[2];
                }
                else if (pointname.Contains("標準件"))
                {
                    kk = "g";
                }
                else if (pointname.Contains("PASS"))
                {
                    kk = "p" + pointname.Split('_')[2];
                }
                else if (pointname.Contains("NG"))
                {
                    kk = "n" + pointname.Split('_')[2];
                }


                string pointup = "";
                string[] ssplit = point.Split(',');
                pointup = ssplit[0].Trim() + "," + ssplit[1].Trim() + "," + Convert.ToString(Convert.ToDouble(ssplit[2].Trim()) + 30) + "," + ssplit[3].Trim() + "," + ssplit[4].Trim() + "," + ssplit[5].Trim();

                textMsgShow.Text = "gop," + kk + "," + pointup;

                sendcmd = "gop," + kk + "," + pointup;
                checkcmd = "";
                Thread th1 = new Thread(new ThreadStart(SendCheck201));
                th1.Start();


                //Produce.Epson.SendCheckRobot("gop," + kk + "," + pointup, "", 0, true, ref error);
            }
        }

        private void btnArm1Cyl_Click(object sender, EventArgs e)
        {
            //if (!Produce.bLoginOK || Produce.UserLevel < 5)
            //{
            //    Program.mainform.ShowWarmForm("未登录或用户权限不足!");
            //    return;
            //}

            //if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            //{
            //    return;
            //}
            //if (btnArm1Cyl.Text == "Arm1气缸ON")
            //{
            //    Program.mainform._myio.SetOutput(0, true);
            //    btnArm1Cyl.Text = "Arm1气缸OFF";
            //}
            //else
            //{
            //    Program.mainform._myio.SetOutput(0, false);
            //    btnArm1Cyl.Text = "Arm1气缸ON";
            //}
        }

        private void bt_GetCurrentPosition_Click(object sender, EventArgs e)
        {
            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }
            Thread th = new Thread(new ThreadStart(getpointthread));
            th.Start();
            //GetPosition();
        }

        private void getpointthread()
        {
            GetPosition();
        }

        private void btnArm2Cyl_Click(object sender, EventArgs e)
        {
            //if (!Produce.bLoginOK || Produce.UserLevel < 5)
            //{
            //    Program.mainform.ShowWarmForm("未登录或用户权限不足!");
            //    return;
            //}
            //if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            //{
            //    return;
            //}

            //if (btnArm1Cyl.Text == "Arm2气缸ON")
            //{
            //    Program.mainform._myio.SetOutput(0, true);
            //    btnArm1Cyl.Text = "Arm2气缸OFF";
            //}
            //else
            //{
            //    Program.mainform._myio.SetOutput(0, false);
            //    btnArm1Cyl.Text = "Arm2气缸ON";
            //}
        }

        private void btnArm1Gass_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (btnArm1Gass.Text == "Arm1吸真空ON")
            {
                //Program.mainform._myio.SetOutput(0, true);
                outnum = 1;
                bonoff = true;
                Thread th1 = new Thread(new ThreadStart(SendCheck202));
                th1.Start();


                btnArm1Gass.Text = "Arm1吸真空OFF";
            }
            else
            {
                //Program.mainform._myio.SetOutput(0, false);
                outnum = 1;
                bonoff = false;
                Thread th1 = new Thread(new ThreadStart(SendCheck202));
                th1.Start();


                btnArm1Gass.Text = "Arm1吸真空ON";
            }
        }

        private void btnArm2Gass_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (btnArm2Gass.Text == "Arm2吸真空ON")
            {
                //Program.mainform._myio.SetOutput(1, true);
                outnum = 2;
                bonoff = true;
                Thread th1 = new Thread(new ThreadStart(SendCheck202));
                th1.Start();


                btnArm2Gass.Text = "Arm2吸真空OFF";
            }
            else
            {
                //Program.mainform._myio.SetOutput(1, false);
                outnum = 2;
                bonoff = false;
                Thread th1 = new Thread(new ThreadStart(SendCheck202));
                th1.Start();
                btnArm2Gass.Text = "Arm2吸真空ON";
            }
        }

        private void btnSafePoint_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !AutoMationTest.Robots.Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (MessageBox.Show("确定进行走位？", "确认", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) == DialogResult.Yes)
            {
                string error = "";
                string kk = "";
                string selectp = comboxSafePoint.SelectedItem.ToString();
                if (selectp.Contains("治具"))
                {
                    kk = selectp.Split('_')[1];
                    if (kk.Length == 1)
                    {
                        kk = "0" + kk;
                    }
                }
                else if (selectp.Contains("投料點"))
                {
                    kk = "t" + selectp.Split('_')[2];
                }
                else if (selectp.Contains("標準件"))
                {
                    kk = "g";
                }
                else if (selectp.Contains("PASS"))
                {
                    kk = "p" + selectp.Split('_')[2];
                }
                else if (selectp.Contains("NG"))
                {
                    kk = "n" + selectp.Split('_')[2];
                }
                else if (selectp.Contains("home"))
                {
                    kk = "home";
                }
                else if (selectp.Contains("PALL"))
                {
                    kk = "pass";
                }
                else if (selectp.Contains("NALL"))
                {
                    kk = "ng";
                }

                textMsgShow.Text = "gosafe," + kk + ",0,0,0,0,0,0";

                sendcmd = "gosafe," + kk + ",0,0,0,0,0,0";
                checkcmd = "";
                Thread th1 = new Thread(new ThreadStart(SendCheck201));
                th1.Start();

                //Produce.Epson.SendCheckRobot("gosafe," + kk + ",0,0,0,0,0,0", "", 0, true, ref error);

            }
        }

        private void PointSetting_FormClosing(object sender, FormClosingEventArgs e)
        {

        }

        bool bclicked = false;

        private void btn_1_0_MouseDown(object sender, MouseEventArgs e)
        {

        }

        private void btn_1_0_MouseUp(object sender, MouseEventArgs e)
        {
            bup = true;
            bclicked = false;
        }

        private void button1_Click(object sender, EventArgs e)
        {
            手柄遙控示意圖 fjog = new 手柄遙控示意圖();
            fjog.Show();
        }

        bool bzhoumove = false;

        private void comboBox1_SelectedIndexChanged(object sender, EventArgs e)
        {
            if (comboBox1.SelectedIndex == 0)
            {
                bzhoumove = false;
            }
            else
            {
                bzhoumove = true;
            }
        }


    }
}
