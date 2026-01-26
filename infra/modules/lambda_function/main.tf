# 1. Zipar o código automaticamente (Adeus zip manual!)
data "archive_file" "code_zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/build/${var.function_name}.zip"
}

# 2. Role de Execução (Permissão Básica)
resource "aws_iam_role" "lambda_exec" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# 3. Permissão para Logs (CloudWatch)
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 4. A Função Lambda em si
resource "aws_lambda_function" "this" {
  function_name    = var.function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = var.handler
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  
  filename         = data.archive_file.code_zip.output_path
  source_code_hash = data.archive_file.code_zip.output_base64sha256
  
  layers = var.layers

  environment {
    variables = var.environment_variables
  }

  tags = var.tags
}

# 5. Log Group (Para definir retenção e não gastar fortunas com logs velhos)
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 7
}