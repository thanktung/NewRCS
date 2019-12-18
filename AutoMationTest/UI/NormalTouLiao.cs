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
    public partial class NormalTouLiao : UserControl
    {
        public NormalTouLiao()
        {
            InitializeComponent();
        }

        public enum formtype
        {
            TouLiao,
            PassZone,
            NGZone
        }

        public enum status
        {
            Empty,
            YouLiao
        }
        private int _id = 0;
        private int _grou = 0;
        private status _status = status.Empty;
        private int _ioindex = 0;
        private formtype _ftype = formtype.TouLiao;

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
            }
        }

        public int Group
        {
            get
            {
                return _grou;
            }
            set
            {
                _grou = value;
            }
        }

        public int IOIndex
        {
            get
            {
                return _ioindex;
            }
            set
            {
                _ioindex = value;
                try
                {
                    SetComboBox(IOLIST, _ioindex - 1);
                }
                catch (Exception ex)
                {
                    SetComboBox(IOLIST, -1);
                }
            }
        }

        public formtype FormType
        {
            get
            {
                return _ftype;
            }
            set
            {
                _ftype = value;
                if (_ftype == formtype.TouLiao)
                {
                    SetBACKCOLOR(SystemColors.GradientInactiveCaption);
                }
                else if (_ftype == formtype.PassZone)
                {
                    SetBACKCOLOR(Color.Green );
                }
                else if (_ftype == formtype.NGZone)
                {
                    SetBACKCOLOR(Color.LightPink);
                }
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

        delegate void dSetComboBox(ComboBox cbox, int index);
        public void SetComboBox(ComboBox cbox, int index)
        {
            if (cbox.InvokeRequired)
            {
                dSetComboBox d = new dSetComboBox(SetComboBox);
                cbox.Invoke(d, new object[] { cbox, index });
            }
            else
            {
                cbox.SelectedIndex = index;

            }
        }

        delegate void dSetBACKCOLOR(Color col);
        public void SetBACKCOLOR(Color col)
        {
            if (this.InvokeRequired)
            {
                dSetBACKCOLOR d = new dSetBACKCOLOR(SetBACKCOLOR);
                this.Invoke(d, new object[] { col });
            }
            else
            {
                this.BackColor = col;
                this.Refresh();

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


        private void button1_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            int selexindex = IOLIST.SelectedIndex;
            if (FormType == formtype.TouLiao)
            {
                Produce.SetTouLiao(Group, this.ID, selexindex + 1);
            }
            else if (FormType == formtype.PassZone)
            {
                Produce.SetPassZone(Group, this.ID, selexindex + 1);
            }
            else if (FormType == formtype.NGZone)
            {
                Produce.SetNGZone(Group, this.ID, selexindex + 1);
            }
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
    }
}
