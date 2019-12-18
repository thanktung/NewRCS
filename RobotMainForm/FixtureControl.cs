using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.UI;
using AutoMationTest.Common;

namespace RobotMainForm
{
    public partial class FixtureControl : UserControl
    {
        public FixtureControl()
        {
            InitializeComponent();
        }

        public void ShowStatus(string status)
        {
            SetTextBoxCallback(textBox_status, status);
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


        private int _stationnumber = 1;
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
                StationNum.Text = _stationnumber.ToString();
            }
        }

        private void button1_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 3)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            if (Program.mainform.allatsui1.ATS[StationNumber - 1].status == TestUI.Status.Testing)
            {
                Program.mainform.ShowWarmForm("ATS測試中請勿操作!");
                return;
            }

            Log.AddManualLog("治具", "更改" + StationNumber.ToString() + "號治具狀態", Program.mainform.allatsui1.ATS[StationNumber - 1].fix_status.ToString(), comboBox1.SelectedItem.ToString());

            if (comboBox1.SelectedItem.ToString() == "Open")
            {
                Program.mainform.allatsui1.ATS[StationNumber - 1].SendFixOpen();
            }
            else if (comboBox1.SelectedItem.ToString() == "Close")
            {
                Program.mainform.allatsui1.ATS[StationNumber - 1].SendFixClose();
            }
        }
    }
}
