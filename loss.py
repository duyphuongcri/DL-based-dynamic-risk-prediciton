import torch
import numpy as np

"""Please compare this with loss_original in docstring
"""


def coxph_logparlk(event_time, event, hazard_ratio):
    """calculate partial likelihood in Cox model
        time invariant hazard, discrete time units

    :param event_time: tensor(batch_size)
    :param event: tensor(batch_size)
    :param hazard_ratio: tensor(batch_size)
    """
    total = torch.tensor(0.0)
    for j in np.unique(event_time).astype(int):
        # H in original code (which subject has event at that time)
        index_j = torch.min(event_time == j, event == 1
        ).nonzero().data.numpy().flatten()
        sum_plus = hazard_ratio[event_time >= j].sum()

        """original paper's version, didn't consider censored sample 
        sum_plus = hazard_ratio[torch.min(event_time >= j, event == 1)].sum()
        """

        if len(index_j) > 0:
            subtotal_1 = torch.log(hazard_ratio)[index_j].sum()
            sum_j = hazard_ratio[index_j].sum()
        else:
            subtotal_1 = torch.tensor(0.0)
            sum_j = torch.tensor(0.0)

        # subtotal_2 = len(index_j) * torch.log(sum_plus)
        #  if no Efron correction considered
        # the Efron correction
        subtotal_2 = torch.tensor(0.0)
        for l in range(len(index_j)):
            subtotal_2 = torch.add(
                torch.log(sum_plus - l * 1.0 / len(index_j) * sum_j),
                subtotal_2)

        total = subtotal_1 - subtotal_2 + total
    return torch.neg(total)


def acc_pairs(event, event_time):
    """calculate accepted pair (i, j)
        i: non-censored event
        j: alive at event_time[i]
    :param event_time: tensor[batch_size]
    :param event: tensor[batch_size]
    """
    event_index = event.nonzero().data.numpy().flatten()
    acc_pair = []
    for i in event_index:
        """original paper didn't consider censor case
        acc_pair += [(i, j) for j in range(len(event)) if event_time[j] > event_time[i]]
        
        In addition: 
        missing: i and j are both event but tie (same event_time)
        """
        acc_pair += [(i, j) for j in np.where(
            np.logical_and(event_time >= event_time[i], event == 0))[0]]
        acc_pair += [(i, j) for j in event_index if
                     event_time[j] > event_time[i]]
    acc_pair.sort(key=lambda x: x[0])
    return acc_pair


def c_index(event, event_time, hazard_ratio):
    """calculate c-index
    :param event_time: tensor(batch_size)
    :param event: tensor(batch_size)
    :param hazard_ratio: tensor(batch_size)
    """
    hazard_ratio = hazard_ratio.data.numpy()
    acc_pair = acc_pairs(event, event_time)
    return sum([hazard_ratio[x[0]] > hazard_ratio[x[1]] for x in
                acc_pair]) * 1.0 / len(acc_pair)


def auc_pairs(event, event_time, horizon):
    """calculate accepted pair (i, j) similar to AUC JM
        i: non-censor event
        j: alive at event_time[j]
    :param event: tensor[batch_size]
    :param event_time: tensor[batch_size]
    :param horizon: delta time
    """
    i_index = event.nonzero().data.numpy().flatten()
    i_index = i_index[np.where(event_time[i_index] <= horizon)].tolist()
    j_index = np.where(event_time > horizon)[0].tolist()

    auc_pair = [(i, j) for i in i_index for j in j_index]
    auc_pair.sort(key=lambda x: x[0])
    return auc_pair


def auc_jm(event, event_time, hazard_ratio, horizon):
    """AUC type c-index in JM package
    :param event_time: tensor(batch_size)
    :param event: tensor(batch_size)
    :param hazard_ratio: tensor(batch_size)
    """
    hazard_ratio = hazard_ratio.data.numpy()
    auc_pair = auc_pairs(event, event_time, horizon)

    return sum([hazard_ratio[x[0]] > hazard_ratio[x[1]] for x in
                auc_pair]) * 1.0 / len(auc_pair)


def dsn_loss(output, time_label, event):
    n_sample = output.size()[0]

    s1 = torch.cat((
        torch.ones(n_sample, 1),
        torch.cumprod(1 - output, dim=1)
    ), dim=1)  # probability of survival to each time point

    loss = torch.tensor(0.0)
    for i in range(n_sample):
        loss = torch.add(loss, torch.log(s1[i, time_label[i]]))
        if event[i] == 1:
            loss = torch.add(
                loss,
                torch.log(output[i, min(time_label[i], output.size()[1] - 1)])
            )

    return torch.neg(loss)
