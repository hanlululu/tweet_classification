# -*- coding: utf-8 -*-
import logging

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from dotenv import find_dotenv, load_dotenv
from sklearn import metrics
from torch import nn
from torch.optim.lr_scheduler import LambdaLR
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AdamW, get_linear_schedule_with_warmup

from src.data.helper import collate_fn, tokenize_function
from src.data.make_dataset import Tweets
from src.models.model import get_model


def accuracy(target, pred):
    '''
    Returns the accuracy of a prediction.

            Parameters:
                    target (1d array): Array of true labels
                    pred (1d array): Array of predicted labels

            Returns:
                    accuracy_score (float): The fraction of correctly classified samples
    '''
    return metrics.accuracy_score(target, pred)

def train(
    model: nn.Module, 
    train_dl: DataLoader, 
    optimizer: torch.optim.Optimizer, 
    scheduler: LambdaLR,
    n_epochs: int, 
    device: torch.device,
):
    '''
    The main training loop which will optimize a given model on a given dataset
    And saves the trained model as my_trained_model.pt in the tweet_classification bucket in the cloud

            Parameters:
                    model (nn.Module): The model being optimized
                    train_dl (DataLoader): The training dataset
                    optimizer (torch.optim.Optimizer): The optimizer used to update the model parameters
                    n_epochs (int): Number of epochs to train for
                    device (torch.device): The device to train on

            Returns:
                    losses (list): List of losses
                    acc (list): List of accuracies 
    '''
    # Keep track of the loss and best accuracy
    losses = []
    acc = []

    # Iterate through epochs
    for ep in range(n_epochs):

        loss_epoch = []

        with tqdm(train_dl, unit="batch") as tepoch:
            # Iterate through each batch in the dataloader
            for batch in train_dl:
                tepoch.set_description(f"Epoch {ep}")

                # VERY IMPORTANT: Make sure the model is in training mode, which turns on 
                # things like dropout and layer normalization
                model.train()

                # VERY IMPORTANT: zero out all of the gradients on each iteration -- PyTorch
                # keeps track of these dynamically in its computation graph so you need to explicitly
                # zero them out
                optimizer.zero_grad()

                # Place each tensor on the GPU
                batch = {b: batch[b].to(device) for b in batch}

                # Pass the inputs through the model, get the current loss and logits
                outputs = model(
                    input_ids=batch['input_ids'],
                    attention_mask=batch['attention_mask'],
                    labels=batch['label']
                )

                log_probs = outputs.logits[0] ## input CR

                if device == torch.cuda.is_available():
                    acc_batch = accuracy(log_probs.softmax(dim=-1).detach().cpu().flatten().numpy()<0.5,batch['label'])
                else: 
                    acc_batch = accuracy(log_probs.softmax(dim=-1).detach().flatten().numpy()<0.5,batch['label'])
                acc.append(acc_batch)


                loss = outputs['loss']
                losses.append(loss.item())
                loss_epoch.append(loss.item())

                # Calculate all of the gradients and weight updates for the model
                loss.backward()
                # Optional: clip gradients
                #torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

                # Finally, update the weights of the model and advance the LR schedule
                optimizer.step()
                scheduler.step()
                #gc.collect()
            
                tepoch.set_postfix(loss=loss.item(), accuracy=acc_batch)

    print(f"The average accuracy is {np.round(np.mean(acc),2)}")
    torch.save(model.state_dict(), "/gcs/tweet_classification/my_trained_model.pt")

    return losses, acc

@click.command()
@click.option("--lr", default=1e-3, help='Learning rate to use for training')
@click.option("--epoch", default=1, help='Number of epoch use for training')
@click.option("--batch_size", default=2, help='Batch size for training')
def train_main(lr, epoch, batch_size):
    '''
    The main training function, with the following tasks:
    Loading model and data
    Tokenizing data
    Setting the optimizer
    Calling the train() function to train the model
    Saving a figure of the loss and accuracy in the tweet_classification bucket in the cloud

            Parameters:
                    lr (float): The learning rate for the optimizer
                    epoch (int): Number of epochs to train for
                    batch_size (int): How many samples per batch to load with the DataLoader

            Returns:
                    Nothing
    '''
    print("Training day and night")
    print(lr)
    print(epoch)
    print(batch_size)

    
    # Load model 
    model = get_model()

    # Define device cpu or gpu
    device = torch.device("cpu")
    if torch.cuda.is_available():
        device = torch.device("cuda")
    print(device)
    model.to(device)

    # Load data
    data_set = Tweets(in_folder="/gcs/tweet_classification/raw", out_folder="/gcs/tweet_classification/processed")
    #data_set = Tweets(in_folder="data/raw", out_folder="data/processed")
    data_set = Dataset.from_pandas(pd.DataFrame({'text':data_set.train_tweet, 'label':data_set.train_label}))

    # Process the data by tokenizing it
    tokenized_dataset = data_set.map(tokenize_function, batched=True, remove_columns=['text'])

    trainloader = DataLoader(tokenized_dataset, shuffle=True, batch_size=batch_size, collate_fn=collate_fn)

    # Define parameters for scheduler
    weight_decay = 0.01
    warmup_steps = 250
    
    # Set optimzer for training model 
    optimizer = AdamW(model.parameters(), lr=lr, betas=(0.9,0.98), eps=1e-6, weight_decay=weight_decay)
    scheduler = get_linear_schedule_with_warmup(
    optimizer,
    warmup_steps,
    epoch * len(trainloader))

    # Train the model 
    losses, acc = train(
    model, 
    trainloader,
    optimizer, 
    scheduler,
    epoch, 
    device)

    _, axis = plt.subplots(2)
  
    # For loss
    axis[0].plot(losses,label="loss")
    axis[0].set_title("Training loss")
    axis[0].set_xlabel("iterations")
    axis[0].set_ylabel("loss")
    
    # For accuracy
    axis[1].plot(acc,label="accuracy")
    axis[1].set_title("Training accuracy")
    axis[0].set_xlabel("iterations")
    axis[0].set_ylabel("loss")

    plt.savefig("/gcs/tweet_classification/training_curve.png")

if __name__ == '__main__':
    log_fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # not used in this stub but often useful for finding various files
    #project_dir = Path(__file__).resolve().parents[2]

    # find .env automagically by walking up directories until it's found, then
    # load up the .env entries as environment variables
    load_dotenv(find_dotenv())

    train_main()




