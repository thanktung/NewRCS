using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using System.Threading;

namespace AutoMationTest.UI
{
    public partial class NormalBuffer : UserControl
    {
        public NormalBuffer()
        {
            InitializeComponent();
        }
        public enum status
        {
            Empty,
            YouLiao
        }

        public enum _buffertype
        {
            WaitTest,
            Retest
        }

        private string _sn = "NONE";
        private int _id = 0;
        private status _status = status.Empty;
        private _buffertype _btype = _buffertype.WaitTest;
        private int _fixnum = 0;
        private string _stationname = "";

        public string SN
        {
            get
            {
                return _sn;
            }
            set
            {
                _sn = value;
                SetTextBoxCallback(tbox_SN, _sn);
            }
        }

        public string StationName
        {
            get
            {
                return _stationname;
            }
            set
            {
                _stationname = value;

            }
        }

        public int FixNum
        {
            get
            {
                return _fixnum;
            }
            set
            {
                _fixnum = value;
                SetTextBoxCallback(tBox_Fix, _fixnum.ToString());
                if (_fixnum == 0)
                {
                    this.Status = status.Empty;
                }
                else
                {
                    this.Status = status.YouLiao;
                }
            }
        }

        public int ID
        {
            get
            {
                return _id;
            }
            set
            {
                _id = value;
                SetButtonCallback(bt_id, _id.ToString());
                //SetTextBoxCallback(tBox_ID, _id.ToString());
            }
        }

        public status Status
        {
            get
            {
                return _status;
            }
            set
            {
                _status = value;
                if (_status == status.Empty)
                {
                    SetJianBianPanelColor(jianBianPanel1, Color.WhiteSmoke, Color.White);
                }
                else
                {
                    SetJianBianPanelColor(jianBianPanel1, Color.Cyan, Color.FromArgb(0, 64, 64));
                }
            }
        }

        public _buffertype BufferType
        {
            get
            {
                return _btype;
            }
            set
            {
                _btype = value;
                if (_btype == _buffertype.WaitTest)
                {
                    SetBackColor(Color.LightCyan);
                }
                else
                {
                    SetBackColor(Color.Linen);
                }
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

        delegate void dSetButtonCallback(Button bt, string msg);
        public void SetButtonCallback(Button bt, string msg)
        {
            if (bt.InvokeRequired)
            {
                dSetButtonCallback d = new dSetButtonCallback(SetButtonCallback);
                bt.Invoke(d, new object[] { bt, msg });
            }
            else
            {
                bt.Text = msg;

            }
        }


        delegate void dSetBackColor(Color col);
        public void SetBackColor(Color col)
        {
            if (this.InvokeRequired)
            {
                dSetBackColor d = new dSetBackColor(SetBackColor);
                this.Invoke(d, new object[] { col });
            }
            else
            {
                this.BackColor = col;
                this.Refresh();

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

            }
        }

        private void NormalBuffer_Load(object sender, EventArgs e)
        {

        }

        private string WarningShowMsg = "";

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

        private void button1_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            int[] Fixlist;
            string _sname = "";

            if (button1.Text == "更改")
            {
                //tBox_ID.Enabled = true;
                tBox_Fix.Enabled = true;
                tbox_SN.Enabled = true;
                button1.Text = "確定";
            }
            else
            {
                this.SN = tbox_SN.Text.Trim();


                if (this.BufferType == _buffertype.WaitTest)
                {
                    string frontStation = "";
                    for (int p = Produce.Station.NameAll.Length - 1; p > -1; p--)
                    {
                        if (Produce.Station.NameAll[p].ToString() == StationName)
                        {
                            if (p > 0)
                            {
                                frontStation = Produce.Station.NameAll[p - 1].ToString();
                                break;
                            }
                        }
                    }

                    Fixlist = (int[])Produce.Station.NumberList[frontStation];
                    _sname = "上一站:" + frontStation;
                }
                else
                {

                    Fixlist = (int[])Produce.Station.NumberList[StationName];
                    _sname = "本站:" + StationName;
                }
                try
                {
                    int setFix = Convert.ToInt32(tBox_Fix.Text);
                    if (Fixlist.Contains(setFix))
                    {
                        this.FixNum = setFix;
                        if (this.BufferType == _buffertype.WaitTest)
                        {
                            Log.AddManualLog("測試狀態", "更改" + StationName + "站" + ID.ToString() + "號待測buffer狀態", "空", "有料-" + FixNum.ToString() + "-" + SN);
                            Produce.SetWaitTestInfo(StationName, this.ID, FixNum, SN);
                        }
                        else
                        {
                            Log.AddManualLog("測試狀態", "更改" + StationName + "站" + ID.ToString() + "號複測buffer狀態", "空", "有料-" + FixNum.ToString() + "-" + SN);
                            Produce.SetReTestInfo(StationName, this.ID, FixNum, SN);
                        }
                    }
                    else
                    {
                        if (setFix == 0)
                        {
                            this.FixNum = setFix;
                            this.SN = "NONE";

                            if (this.BufferType == _buffertype.WaitTest)
                            {
                                Log.AddManualLog("測試狀態", "更改" + StationName + "站" + ID.ToString() + "號待測buffer狀態", "有料", "空");
                                Produce.SetWaitTestInfo(StationName, this.ID, FixNum, SN);
                            }
                            else
                            {
                                Log.AddManualLog("測試狀態", "更改" + StationName + "站" + ID.ToString() + "號複測buffer狀態", "有料", "空");
                                Produce.SetReTestInfo(StationName, this.ID, FixNum, SN);
                            }
                        }
                        else
                        {
                            MessageBox.Show("輸入的治具編號不在 " + _sname + " 站內 ( " + Fixlist[0].ToString() + " ~ " + Fixlist[Fixlist.Length - 1].ToString() + " )");
                            return;
                        }
                    }
                    tBox_Fix.Enabled = false;
                    tbox_SN.Enabled = false;
                    button1.Text = "更改";
                }
                catch (Exception ex)
                {
                    MessageBox.Show("輸入的不是數字");
                }
            }
        }

    }
}
