using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;

namespace AutoMationTest.UI
{
    public partial class QueueShow : UserControl
    {
        Mutex M1;
        public int Count = 0;
        public QueueShow()
        {
            InitializeComponent();
            //this.Count = nCount;
            this.DoubleBuffered = true;

            if (!Produce.bAlreadyGetStationInfo)
            {
                Produce.GetStationInfo();
            }

            M1 = new Mutex();
        }
        Button[] buttons;
        private void QueueShow_Load(object sender, EventArgs e)
        {


            Count = Common.Produce.Station.Count + 1;
            buttons = new Button[Count];

            for (int i = 0; i < Count; i++)
            {
                buttons[i] = new Button();
                buttons[i].FlatStyle = FlatStyle.Flat;
                buttons[i].FlatAppearance.BorderSize = 0;
                buttons[i].Text = "";
                buttons[i].Font = new Font("Microsoft YaHei", (float)12, FontStyle.Bold);
                buttons[i].Size = new Size(100, 50);
                buttons[i].TextAlign = ContentAlignment.MiddleLeft;
                buttons[i].Location = new Point(150, 55 + 55 * i);
                this.Controls.Add(buttons[i]);
            }
        }

        delegate void dShowQueueCount(int count);
        public void ShowQueueCount(int count)
        {
            if (QueueCount.InvokeRequired)
            {
                dShowQueueCount d = new dShowQueueCount(ShowQueueCount);
                QueueCount.Invoke(d, new object[] { count });
            }
            else
            {
                if (QueueCount.Text != count.ToString())
                    QueueCount.Text = count.ToString();
                QueueCount.Refresh();
            }
        }

        delegate void dSetQueueStatus(int num, TestUI.Action e);
        public void SetQueueStatus(int num, TestUI.Action e)
        {
            if (buttons[num].InvokeRequired)
            {
                dSetQueueStatus d = new dSetQueueStatus(SetQueueStatus);
                buttons[num].Invoke(d, new object[] { num, e });
            }
            else
            {
                Color cl = Color.Black;
                string text = "";
                switch (e.robotCmd)
                {
                    case Common.Produce.RobotCMD.PASS:
                        cl = Color.Lime;
                        text = "PASS";
                        break;
                    case Common.Produce.RobotCMD.NG:
                        cl = Color.Red;
                        text = "NG";
                        break;
                    //case Common.Produce.RobotCMD.Pick:
                    //    cl = Color.Black;
                    //    text = "抓板";
                    //    break;
                    case Common.Produce.RobotCMD.Put:
                        cl = Color.Purple;
                        text = "放板";
                        break;
                    case Common.Produce.RobotCMD.Retest:
                        cl = Color.DarkSalmon;
                        text = "複測";
                        break;

                    case Common.Produce.RobotCMD.ChouJian:
                        cl = Color.Yellow;
                        text = "抽測";
                        break;
                }

                buttons[num].Text = e.StationNumber + " : " + text;
                if (buttons[num].ForeColor != cl)
                {
                    buttons[num].ForeColor = cl;
                    buttons[num].Refresh();
                }
            }
        }
        delegate void dClearQueueStatus(int num);
        public void ClearQueueStatus(int num)
        {
            if (buttons[num].InvokeRequired)
            {
                dClearQueueStatus d = new dClearQueueStatus(ClearQueueStatus);
                buttons[num].Invoke(d, new object[] { num });
            }
            else
            {
                if (buttons[num].Text != "")
                    buttons[num].Text = "";
            }
        }

        public void ShowStatus()
        {
            M1.WaitOne();
            for (int m = 0; m < this.Count; m++)
            {
                int count = Produce.QUEUE.GetQueueLength();
                ShowQueueCount(count);
                if (m < count)
                {
                    SetQueueStatus(m, Produce.QUEUE[m]);
                }
                else
                    ClearQueueStatus(m );
            }
            M1.ReleaseMutex();
        }
    }
}
