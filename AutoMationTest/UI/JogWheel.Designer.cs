namespace AutoMationTest.UI
{
    partial class JogWheel
    {
        /// <summary> 
        /// 設計工具所需的變數。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清除任何使用中的資源。
        /// </summary>
        /// <param name="disposing">如果應該處置 Managed 資源則為 true，否則為 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 元件設計工具產生的程式碼

        /// <summary> 
        /// 此為設計工具支援所需的方法 - 請勿使用程式碼編輯器
        /// 修改這個方法的內容。
        /// </summary>
        private void InitializeComponent()
        {
            this.ov_back = new Microsoft.VisualBasic.PowerPacks.OvalShape();
            this.shapeContainer1 = new Microsoft.VisualBasic.PowerPacks.ShapeContainer();
            this.ov_front = new Microsoft.VisualBasic.PowerPacks.OvalShape();
            this.SuspendLayout();
            // 
            // ov_back
            // 
            this.ov_back.BorderColor = System.Drawing.Color.DarkCyan;
            this.ov_back.BorderWidth = 2;
            this.ov_back.FillColor = System.Drawing.Color.WhiteSmoke;
            this.ov_back.FillGradientColor = System.Drawing.Color.FromArgb(((int)(((byte)(128)))), ((int)(((byte)(255)))), ((int)(((byte)(255)))));
            this.ov_back.FillGradientStyle = Microsoft.VisualBasic.PowerPacks.FillGradientStyle.Central;
            this.ov_back.FillStyle = Microsoft.VisualBasic.PowerPacks.FillStyle.Solid;
            this.ov_back.Location = new System.Drawing.Point(1, 1);
            this.ov_back.Name = "ov_back";
            this.ov_back.Size = new System.Drawing.Size(120, 120);
            // 
            // shapeContainer1
            // 
            this.shapeContainer1.Location = new System.Drawing.Point(0, 0);
            this.shapeContainer1.Margin = new System.Windows.Forms.Padding(0);
            this.shapeContainer1.Name = "shapeContainer1";
            this.shapeContainer1.Shapes.AddRange(new Microsoft.VisualBasic.PowerPacks.Shape[] {
            this.ov_front,
            this.ov_back});
            this.shapeContainer1.Size = new System.Drawing.Size(126, 126);
            this.shapeContainer1.TabIndex = 0;
            this.shapeContainer1.TabStop = false;
            // 
            // ov_front
            // 
            this.ov_front.BackColor = System.Drawing.Color.Blue;
            this.ov_front.BorderColor = System.Drawing.Color.Black;
            this.ov_front.BorderWidth = 4;
            this.ov_front.FillColor = System.Drawing.Color.Black;
            this.ov_front.FillGradientColor = System.Drawing.Color.WhiteSmoke;
            this.ov_front.FillGradientStyle = Microsoft.VisualBasic.PowerPacks.FillGradientStyle.Central;
            this.ov_front.FillStyle = Microsoft.VisualBasic.PowerPacks.FillStyle.Solid;
            this.ov_front.Location = new System.Drawing.Point(19, 19);
            this.ov_front.Name = "ov_front";
            this.ov_front.Size = new System.Drawing.Size(83, 83);
            // 
            // JogWheel
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.Color.Transparent;
            this.Controls.Add(this.shapeContainer1);
            this.Name = "JogWheel";
            this.Size = new System.Drawing.Size(126, 126);
            this.Load += new System.EventHandler(this.JogWheel_Load);
            this.ResumeLayout(false);

        }

        #endregion

        private Microsoft.VisualBasic.PowerPacks.OvalShape ov_back;
        private Microsoft.VisualBasic.PowerPacks.ShapeContainer shapeContainer1;
        private Microsoft.VisualBasic.PowerPacks.OvalShape ov_front;

    }
}
