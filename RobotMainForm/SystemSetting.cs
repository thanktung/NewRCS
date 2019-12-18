using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;
using AutoMationTest.UI;

namespace RobotMainForm
{
    public partial class SystemSetting : Form
    {
        public SystemSetting()
        {
            InitializeComponent();
        }

        private string WarningShowMsg = "";
        Point pt;
        PictureBox pb = new PictureBox();
        delegate void dSetpicbox(PictureBox pb, bool bshow);
        public void Setpicbox(PictureBox pb, bool bshow)
        {
            if (pb.InvokeRequired)
            {
                dSetpicbox d = new dSetpicbox(Setpicbox);
                pb.Invoke(d, new object[] { pb, bshow });
            }
            else
            {
                pb.Visible = bshow;
            }
        }

        delegate void dSetpicboxLocation(PictureBox pb, Point point);
        public void SetpicboxLocation(PictureBox pb, Point point)
        {
            if (pb.InvokeRequired)
            {
                dSetpicboxLocation d = new dSetpicboxLocation(SetpicboxLocation);
                pb.Invoke(d, new object[] { pb, point });
            }
            else
            {
                pb.Location = point;
                pb.Refresh();
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
            Thread.Sleep(500);
            wf.Close();
        }

        private void SetOKThread()
        {
            Setpicbox(pb, true);
            //for (int i = 0; i < 10; i++)
            //{
            //    SetpicboxLocation(pb, new Point(pt.X, pt.Y - i * 2));
            //    Thread.Sleep(10);
            //}
            Thread.Sleep(100);
            Setpicbox(pb, false);
            //SetpicboxLocation(pb, pt);
        }

        private void SystemSetting_Load(object sender, EventArgs e)
        {

            numericUpDown1.Value = Convert.ToDecimal(Produce.LianxuWarningCount);
            checkBox1.Checked = Produce.WarningStopUse;
            numericUpDown2.Value = Convert.ToDecimal(Produce.pcruntimeset[0]);
            numericUpDown3.Value = Convert.ToDecimal(Produce.pcruntimeset[1]);
            numericUpDown3.Value = Convert.ToDecimal(Produce.pcruntimeset[1]);
            numericUpDown4.Value = Convert.ToDecimal(Produce.LoginTimeOut);
            if (Produce.GoldenNG_SwitchMode)
            {
                radioButton1.Checked = true;
            }
            else
            {
                radioButton2.Checked = true;
            }

            if (Produce.bNotUseSafeDoor)
            {
                checkBox_usesafedoor.Checked = false;
            }
            else
            {
                checkBox_usesafedoor.Checked = true;
            }
        }

        private void bt_setng_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            pt = pictureBox1.Location;
            pb = pictureBox1;
            int count = Convert.ToInt32(numericUpDown1.Value);
            bool bstopuse = checkBox1.Checked;
            Log.AddManualLog("系統參數", "更改連續NG設定", Produce.LianxuWarningCount.ToString() + "-" + Produce.WarningStopUse.ToString(), count.ToString() + "-" + bstopuse.ToString());

            Produce.SetLianXuNG(count, bstopuse);

            Thread thok = new Thread(new ThreadStart(SetOKThread));
            thok.Start();
        }

        private void bt_setpctime_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            pt = pictureBox2.Location;
            pb = pictureBox2;
            int hour = Convert.ToInt32(numericUpDown2.Value);
            int minute = Convert.ToInt32(numericUpDown3.Value);
            Log.AddManualLog("系統參數", "更改PC運行時間管控", Produce.pcruntimeset[0] + "天" + Produce.pcruntimeset[1] + "時", hour.ToString() + "天" + minute.ToString() + "時");
            Produce.SetPCRuntime(hour, minute);
            Thread thok = new Thread(new ThreadStart(SetOKThread));
            thok.Start();
        }

        private void bt_setlogintimeout_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            pt = pictureBox3.Location;
            pb = pictureBox3;
            int timeout = Convert.ToInt32(numericUpDown4.Value);
            Log.AddManualLog("系統參數", "更改超時登出時間", Produce.LoginTimeOut.ToString() + "分鐘", timeout.ToString() + "分鐘");
            Produce.SetLoginTimeOut(timeout);
            Thread thok = new Thread(new ThreadStart(SetOKThread));
            thok.Start();
        }

        private void bt_goldenngset_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            pt = pictureBox4.Location;
            pb = pictureBox4;
            int timeout = Convert.ToInt32(numericUpDown4.Value);
            Log.AddManualLog("系統參數", "更改標準件NG後是否切換正常模式", Produce.GoldenNG_SwitchMode.ToString(), radioButton1.Checked.ToString());

            Produce.SetGoldenNGSwitchMode(radioButton1.Checked);

            Thread thok = new Thread(new ThreadStart(SetOKThread));
            thok.Start();
        }

        private void checkBox_usesafedoor_CheckedChanged(object sender, EventArgs e)
        {

        }

        private void bt_changesafedooruse_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 4)
            {
                if (checkBox_usesafedoor.Checked)
                {
                    if (Produce.bNotUseSafeDoor)
                        checkBox_usesafedoor.Checked = false;
                }
                else
                {
                    if (!Produce.bNotUseSafeDoor)
                        checkBox_usesafedoor.Checked = true;
                }

                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            pt = pictureBox5.Location;
            pb = pictureBox5;
            Log.AddManualLog("系統參數", "更改是否停用安全門", Convert.ToString(!Produce.bNotUseSafeDoor), checkBox_usesafedoor.Checked.ToString());

            if (checkBox_usesafedoor.Checked)
            {
                Produce.bNotUseSafeDoor = false;
            }
            else
            {
                Produce.bNotUseSafeDoor = true;
            }

            Thread thok = new Thread(new ThreadStart(SetOKThread));
            thok.Start();
        }
    }
}
