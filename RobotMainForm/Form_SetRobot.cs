using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using AutoMationTest.Common;
using AutoMationTest.Robots;

namespace RobotMainForm
{
    public partial class Form_SetRobot : Form
    {
        public Form_SetRobot()
        {
            InitializeComponent();
        }



        private void Form_SetRobot_Load(object sender, EventArgs e)
        {
            INI.RobotSettings _rsetting = new INI.RobotSettings();
            INI.ReadRobotSetting(Robot.RobotType.Epson, ref _rsetting);

            textBox_Epson_IP.Text = _rsetting.IP;
            textBox_Epson_Pwd.Text = _rsetting.LoginPassword;
            textBox_Epson_SysPort.Text = _rsetting.SystemPort.ToString();
            textBox_Epson_UserPort.Text = _rsetting.UserPort.ToString();

            if (_rsetting.UserPort2 == 0)
            {
                textBox_Epson_UserPort2.Text = "";
            }
            else
            {
                textBox_Epson_UserPort2.Text = _rsetting.UserPort2.ToString();
            }
        }

        private void bt_setepson_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }


            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }

            INI.RobotSettings _rsetting = new INI.RobotSettings();
            _rsetting.IP = textBox_Epson_IP.Text;
            _rsetting.LoginPassword = textBox_Epson_Pwd.Text;
            try
            {
                _rsetting.SystemPort = Convert.ToInt32(textBox_Epson_SysPort.Text);
            }
            catch (Exception ex)
            {
                textBox_Epson_SysPort.Text = "";
                return;
            }
            try
            {
                _rsetting.UserPort = Convert.ToInt32(textBox_Epson_UserPort.Text);
            }
            catch (Exception ex)
            {
                textBox_Epson_UserPort.Text = "";
                return;
            }

            try
            {
                _rsetting.UserPort2 = Convert.ToInt32(textBox_Epson_UserPort2.Text);
            }
            catch (Exception ex)
            {
                textBox_Epson_UserPort2.Text = "";
                _rsetting.UserPort2 = 0;
            }

            INI.WriteRobotSetting(Robot.RobotType.Epson, _rsetting);

            if (Produce.Epson != null)
            {
                Produce.Epson.Dispose();
                Produce.Epson = null;
            }

            Produce.Epson = new Robot(Robot.RobotType.Epson);
        }

        private void button2_Click(object sender, EventArgs e)
        {
            textBox3.Text = Robot.ReceiveMSG_From_Robot;
        }

        private void button9_Click(object sender, EventArgs e)
        {
            if (!Produce.bLoginOK || Produce.UserLevel < 5)
            {
                Program.mainform.ShowWarmForm("未登录或用户权限不足!");
                return;
            }
            if (Produce.Epson == null || !Robot.IsConnected)
            {
                Program.mainform.ShowWarmForm("手臂未連接!");
            }

            if (!Program.mainform.bPaused)
            {
                Program.mainform.ShowWarmForm("程式運行中請勿操作!");
                return;
            }
            string serror = "";
            Produce.Epson.SendCheckRobot(textBox2.Text.Trim(), "", 0, true, ref serror);
        }
    }
}
