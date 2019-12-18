using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using MySql.Data.MySqlClient;
using AutoMationTest.Common;

namespace RobotMainForm
{
    public partial class LoginForm : Form
    {
        public LoginForm()
        {
            InitializeComponent();
        }

        private void button1_Click(object sender, EventArgs e)
        {
            string username = textBox1.Text;
            string password = textBox2.Text;
            try
            {

           //     string sConnCmd = @"server=172.23.250.250;user id=root;Password=123456;DataBase=serverlogin";
                string sConnCmd = @"server=10.150.20.6;user id=root;Password=;DataBase=serverlogin";
                MySqlConnection MYSqlconn = new MySqlConnection(sConnCmd);
                MYSqlconn.Open();//先開啟連接
                ConnectionState con_status = MYSqlconn.State;
                if (con_status.ToString().ToLower() != "open")
                {
                    Produce.LoginName = username;
                    Produce.UserJob = "未聯網";
                    Produce.bLoginOK = true;
                    Produce.UserLevel = 2;
                    this.Close();
                }
                else
                {
                    string SQL_QUERY_NAME_JOB_FROM_USERS_BY_USERNAME = "Select name,job,level from user where wncid='" + username + "' and password='" + password + "'";
                    DataSet set = new DataSet();
                    MySqlCommand sMYSqlCmd = new MySqlCommand(SQL_QUERY_NAME_JOB_FROM_USERS_BY_USERNAME, MYSqlconn);
                    MySqlDataReader DataReader = sMYSqlCmd.ExecuteReader();
                    set.Load(DataReader, LoadOption.OverwriteChanges, new string[] { "users" });
                    DataReader.Close();

                    if (set.Tables[0].Rows.Count > 0)
                    {
                        object[] aa = set.Tables[0].Rows[0].ItemArray;
                        Produce.LoginName = aa[0].ToString();
                        Produce.UserJob = aa[1].ToString();
                        Produce.UserLevel = Convert.ToInt16(aa[2]);
                        Produce.bLoginOK = true;
                    }
                    else
                    {
                        //this.label3.Text = "登錄失敗！ ";
                        textBox1.Text = "";
                        textBox2.Text = "";
                        Produce.LoginName = "";
                        Produce.UserJob = "";
                        Produce.bLoginOK = false;
                        Produce.UserLevel = 0;
                    }
                    MYSqlconn.Close();
                }
                if (Produce.bLoginOK)
                {
                    this.Close();
                }
            }
            catch (Exception)
            {
                Produce.LoginName = "";
                Produce.UserJob = "";
                Produce.bLoginOK = false;
                Produce.UserLevel = 0;

            }
        }

        private void textBox2_TextChanged(object sender, EventArgs e)
        {

        }

        private void textBox2_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                button1.PerformClick();
            }
        }

        private void textBox1_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                textBox2.Focus();
            }
        }
    }
}
