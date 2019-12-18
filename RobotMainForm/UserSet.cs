using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using MySql.Data.MySqlClient;

namespace RobotMainForm
{
    public partial class UserSet : Form
    {
        public UserSet()
        {
            InitializeComponent();
        }

        private void button1_Click(object sender, EventArgs e)
        {
            if (t_verify.Text.Trim() != "Passw@rd123")
            {
                MessageBox.Show("主管Approve code 錯誤");
                t_verify.Text = "";
                return;
            }

            if (t_id.Text.Length < 7)
            {
                MessageBox.Show("工號長度不正確");
                t_id.Text = "";
                return;
            }

            if (t_name.Text.Trim() == "")
            {
                MessageBox.Show("名稱不能為空");
                t_name.Text = "";
                return;
            }

            if (t_pwd.Text.Trim() == "")
            {
                MessageBox.Show("密碼不能為空");
                return;
            }

            if (t_pwd.Text != t_pwd2.Text)
            {
                MessageBox.Show("兩次密碼不匹配");
                return;
            }

            if (comboBox1.SelectedIndex < 0)
            {
                MessageBox.Show("職位不能為空");
                return;
            }

            try
            {
              //  string sConnCmd = @"server=172.23.250.250;user id=root;Password=123456;DataBase=serverlogin";
                string sConnCmd = @"server=10.150.20.6;user id=root;Password=;DataBase=serverlogin";
                MySqlConnection MYSqlconn = new MySqlConnection(sConnCmd);
                MYSqlconn.Open();//先開啟連接
                ConnectionState con_status = MYSqlconn.State;
                if (con_status.ToString().ToLower() != "open")
                {
                    MessageBox.Show("未聯網,無法註冊");
                    return;
                }
                else
                {

                    string loginid = t_id.Text.Trim();
                    string name = t_name.Text.Trim();
                    string pwd = t_pwd.Text.Trim();
                    string job = comboBox1.SelectedItem.ToString();
                    int level = 0;
                    switch (comboBox1.SelectedIndex)
                    {
                        case 0:
                            level = 2;
                            break;
                        case 1:
                            level = 3;
                            break;
                        case 2:
                            level = 4;
                            break;
                        case 3:
                            level = 4;
                            break;
                        case 4:
                            level = 4;
                            break;
                        case 5:
                            level = 2;
                            break;
                        default:
                            level = 0;
                            break;
                    }

                    string cmd1 = "Select wncid from user where wncid='" + loginid + "'";
                    DataSet set = new DataSet();
                    MySqlCommand sMYSqlCmd = new MySqlCommand(cmd1, MYSqlconn);
                    MySqlDataReader DataReader = sMYSqlCmd.ExecuteReader();
                    set.Load(DataReader, LoadOption.OverwriteChanges, new string[] { "users" });
                    DataReader.Close();

                    if (set.Tables[0].Rows.Count > 0)
                    {
                        MessageBox.Show("此工號已註冊!");
                        t_id.Text = "";
                        return;
                    }

                    string cmd2 = "Select name from user where name='" + name + "'";
                    set = new DataSet();
                    sMYSqlCmd = new MySqlCommand(cmd2, MYSqlconn);
                    DataReader = sMYSqlCmd.ExecuteReader();
                    set.Load(DataReader, LoadOption.OverwriteChanges, new string[] { "users" });
                    DataReader.Close();

                    if (set.Tables[0].Rows.Count > 0)
                    {
                        MessageBox.Show("此名稱已註冊!");
                        t_name.Text = "";
                        return;
                    }

                    string cmd3 = "INSERT INTO user (wncid,name,password,job,level) VALUES ('" + loginid + "','" + name + "','" + pwd + "','" + job + "','" + level + "')";
                    sMYSqlCmd = new MySqlCommand(cmd3, MYSqlconn);
                    DataReader = sMYSqlCmd.ExecuteReader();
                    DataReader.Close();

                    MessageBox.Show("註冊成功!");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("註冊異常,請聯繫SE Ricard");
            }
        }

        private void t_id_TextChanged(object sender, EventArgs e)
        {
            try
            {
                int d = Convert.ToInt32(t_id.Text);
            }
            catch (Exception ex)
            {
                t_id.Text = "";
            }

            if (t_id.Text.Length > 8)
            {
                t_id.Text = "";
            }
        }

        private void t_pwd2_TextChanged(object sender, EventArgs e)
        {
            if (t_pwd2.Text != t_pwd.Text)
            {
                label_CheckPassword.Text = "*兩次密碼不匹配";
            }
            else
            {
                label_CheckPassword.Text = "";
            }
        }
    }
}
